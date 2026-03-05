"""
파싱 결과를 Neo4j에 영속화하는 모듈 (Memory-First).

모든 파일의 파싱 결과를 메모리에 축적한 뒤,
관계 해석까지 완료한 후 일괄로 DB에 기록합니다.
UNWIND 배치 쿼리로 DB 라운드트립을 최소화하여 대규모 소스코드도 효율적으로 처리합니다.
"""
import json
import logging
from dataclasses import asdict

from graph_db.client import DBClient

from .models import (
    ParsedType, ParsedField, ParsedMethod, ParsedFileResult,
    ParsedCallEdge, ParsedParameterEdge, ParsedReturnEdge,
)

logger = logging.getLogger(__name__)


class GraphWriter:
    """
    [그래프 DB 라이터 — Memory-First 방식]

    사용 흐름:
      1. collect(result)  — 파일별 파싱 결과를 메모리에 축적 (DB 접근 없음)
      2. flush()          — 축적된 전체 데이터를 일괄 DB 기록

    모든 노드가 메모리에 존재하는 상태에서 관계를 해석하므로,
    파일 처리 순서에 의존하지 않고 정확한 관계를 생성할 수 있습니다.
    """

    def __init__(self, connector: DBClient):
        self.connector = connector

        # --- 노드 메모리 저장소 ---
        self._types: dict[str, ParsedType] = {}         # qualname → ParsedType
        self._fields: dict[str, ParsedField] = {}       # qualname → ParsedField
        self._methods: dict[str, ParsedMethod] = {}     # qualname → ParsedMethod

        # --- 엣지 메모리 저장소 ---
        self._calls: list[ParsedCallEdge] = []
        self._param_edges: list[ParsedParameterEdge] = []
        self._return_edges: list[ParsedReturnEdge] = []

    # -----------------------------------------------------------------------
    # 수집 (DB 접근 없음)
    # -----------------------------------------------------------------------

    def collect(self, result: ParsedFileResult):
        """파싱 결과를 메모리에 축적합니다. DB 접근 없음."""
        for t in result.types:
            self._types[t.qualname] = t
        for f in result.fields:
            self._fields[f.qualname] = f
        for m in result.methods:
            self._methods[m.qualname] = m
        self._calls.extend(result.calls)
        self._param_edges.extend(result.parameter_edges)
        self._return_edges.extend(result.return_edges)

    # -----------------------------------------------------------------------
    # 일괄 기록 (UNWIND 배치)
    # -----------------------------------------------------------------------

    def flush(self):
        """메모리에 축적된 전체 데이터를 UNWIND 배치로 일괄 DB에 기록합니다."""
        logger.info(
            f"Flushing to DB: {len(self._types)} types, "
            f"{len(self._fields)} fields, {len(self._methods)} methods, "
            f"{len(self._calls)} calls, {len(self._param_edges)} params, "
            f"{len(self._return_edges)} returns"
        )

        # 1단계: 노드 생성
        self._flush_types()
        self._flush_fields()
        self._flush_methods()

        # 2단계: 엣지 해석을 위한 인메모리 인덱스 구축
        self._build_indexes()

        # 3단계: 엣지 생성
        self._flush_parameter_edges()
        self._flush_return_edges()
        self._flush_calls()

        # 메모리 정리
        self._clear()
        logger.info("Flush complete.")

    # -----------------------------------------------------------------------
    # 노드 Flush
    # -----------------------------------------------------------------------

    def _flush_types(self):
        """축적된 TYPE 노드를 UNWIND 배치로 일괄 DB에 기록합니다."""
        if not self._types:
            return

        batch = []
        for t in self._types.values():
            row = asdict(t)
            # list[ConstantInfo] → JSON 문자열
            row["constants"] = json.dumps(row["constants"], ensure_ascii=False) if row["constants"] else ""
            batch.append(row)

        try:
            self.connector.execute_query("""
                UNWIND $batch AS row
                MERGE (t:TYPE {qualname: row.qualname})
                SET t.name = row.name,
                    t.kind = row.kind,
                    t.constants = row.constants
                WITH t, row
                MATCH (f:FILE {path: row.file_path})
                MERGE (f)-[:CONTAINS]->(t)
            """, {"batch": batch})
        except Exception as e:
            logger.error(f"Failed to batch upsert TYPEs: {e}")

    def _flush_fields(self):
        """축적된 FIELD 노드를 UNWIND 배치로 일괄 DB에 기록합니다."""
        if not self._fields:
            return

        batch = []
        for f in self._fields.values():
            row = asdict(f)
            # TypeInfo → JSON 문자열, 키명을 DB 스키마에 맞춤 (field_type → type)
            row["type"] = json.dumps(row.pop("field_type"), ensure_ascii=False)
            batch.append(row)

        try:
            self.connector.execute_query("""
                UNWIND $batch AS row
                MERGE (f:FIELD {qualname: row.qualname})
                SET f.name = row.name,
                    f.type = row.type,
                    f.constraint = row.constraint
                WITH f, row
                MATCH (t:TYPE {qualname: row.type_qualname})
                MERGE (t)-[:CONTAINS]->(f)
            """, {"batch": batch})
        except Exception as e:
            logger.error(f"Failed to batch upsert FIELDs: {e}")

    def _flush_methods(self):
        """축적된 METHOD 노드를 UNWIND 배치로 일괄 DB에 기록합니다."""
        if not self._methods:
            return

        batch = []
        for m in self._methods.values():
            row = asdict(m)
            # list[ParamInfo] → JSON 문자열
            row["params"] = json.dumps(row["params"], ensure_ascii=False)
            # TypeInfo|None → JSON 문자열
            row["return_type"] = json.dumps(row["return_type"], ensure_ascii=False) if row["return_type"] else ""
            # 키명을 DB 스키마에 맞춤 (method_hash → hash, scan_id → last_scan_id)
            row["hash"] = row.pop("method_hash")
            row["last_scan_id"] = row.pop("scan_id") or ""
            batch.append(row)

        try:
            self.connector.execute_query("""
                UNWIND $batch AS row
                MERGE (m:METHOD {qualname: row.qualname})
                ON CREATE SET m.status = 'NEW'
                ON MATCH SET m.status = CASE
                    WHEN m.hash = row.hash THEN 'AS-IS'
                    ELSE 'MODIFIED'
                END
                SET m.name = row.name,
                    m.signature = row.signature,
                    m.source = row.source,
                    m.hash = row.hash,
                    m.params = row.params,
                    m.return_type = row.return_type,
                    m.endpoint_uri = row.endpoint_uri,
                    m.http_method = row.http_method,
                    m.last_scan_id = row.last_scan_id
                WITH m, row
                MATCH (t:TYPE {qualname: row.class_qualname})
                MERGE (t)-[:CONTAINS]->(m)
            """, {"batch": batch})
        except Exception as e:
            logger.error(f"Failed to batch upsert METHODs: {e}")

    # -----------------------------------------------------------------------
    # 인메모리 인덱스 구축
    # -----------------------------------------------------------------------

    def _build_indexes(self):
        """엣지 해석에 필요한 인메모리 인덱스를 구축합니다."""
        # name → qualname (동명 타입 시 마지막 등록이 우선 — 향후 개선 대상)
        self._type_by_name: dict[str, str] = {
            t.name: t.qualname for t in self._types.values()
        }
        # class_qualname → {method_name → [ParsedMethod]}
        self._methods_by_class: dict[str, dict[str, list[ParsedMethod]]] = {}
        for m in self._methods.values():
            cls = self._methods_by_class.setdefault(m.class_qualname, {})
            cls.setdefault(m.name, []).append(m)

        # class_qualname → {field_name → ParsedField}
        self._fields_by_class: dict[str, dict[str, ParsedField]] = {}
        for f in self._fields.values():
            cls = self._fields_by_class.setdefault(f.type_qualname, {})
            cls[f.name] = f

    # -----------------------------------------------------------------------
    # 엣지 Flush (UNWIND 배치)
    # -----------------------------------------------------------------------

    def _flush_parameter_edges(self):
        """HAS_PARAMETER 엣지를 UNWIND 배치로 일괄 DB에 기록합니다."""
        # Python에서 미리 resolve하여 (method_qualname, type_qualname) 쌍 수집
        batch = []
        for edge in self._param_edges:
            for type_name in edge.param_info["type"]["layout"]:
                type_qualname = self._type_by_name.get(type_name)
                if type_qualname:
                    batch.append({
                        "method_qualname": edge.method_qualname,
                        "type_qualname": type_qualname,
                    })

        if not batch:
            return

        try:
            self.connector.execute_query("""
                UNWIND $batch AS row
                MATCH (m:METHOD {qualname: row.method_qualname})
                MATCH (t:TYPE {qualname: row.type_qualname})
                MERGE (m)-[:HAS_PARAMETER]->(t)
            """, {"batch": batch})
        except Exception as e:
            logger.error(f"Failed to batch upsert HAS_PARAMETER edges: {e}")

    def _flush_return_edges(self):
        """RETURNS 엣지를 UNWIND 배치로 일괄 DB에 기록합니다."""
        batch = []
        for edge in self._return_edges:
            for type_name in edge.return_info["layout"]:
                type_qualname = self._type_by_name.get(type_name)
                if type_qualname:
                    batch.append({
                        "method_qualname": edge.method_qualname,
                        "type_qualname": type_qualname,
                    })

        if not batch:
            return

        try:
            self.connector.execute_query("""
                UNWIND $batch AS row
                MATCH (m:METHOD {qualname: row.method_qualname})
                MATCH (t:TYPE {qualname: row.type_qualname})
                MERGE (m)-[:RETURNS]->(t)
            """, {"batch": batch})
        except Exception as e:
            logger.error(f"Failed to batch upsert RETURNS edges: {e}")

    def _flush_calls(self):
        """CALLS 엣지를 해석하고 UNWIND 배치로 일괄 DB에 기록합니다."""
        resolved_batch = []
        external_batch = []

        # Python에서 호출 대상을 미리 resolve한 뒤 두 배치로 분리
        for call in self._calls:
            target_qualname = self._resolve_call_target(
                call.caller_qualname, call.target_method_name, call.object_name,
            )
            if target_qualname:
                resolved_batch.append({
                    "caller_qualname": call.caller_qualname,
                    "callee_qualname": target_qualname,
                })
            else:
                ext_qualname = (
                    f"{call.object_name}.{call.target_method_name}"
                    if call.object_name
                    else call.target_method_name
                )
                external_batch.append({
                    "caller_qualname": call.caller_qualname,
                    "ext_qualname": ext_qualname,
                    "name": call.target_method_name,
                    "signature": f"{ext_qualname}()",
                })

        # resolved: METHOD → CALLS → METHOD
        if resolved_batch:
            try:
                self.connector.execute_query("""
                    UNWIND $batch AS row
                    MATCH (caller:METHOD {qualname: row.caller_qualname})
                    MATCH (callee:METHOD {qualname: row.callee_qualname})
                    MERGE (caller)-[:CALLS]->(callee)
                """, {"batch": resolved_batch})
            except Exception as e:
                logger.error(f"Failed to batch upsert CALLS (resolved) edges: {e}")

        # external: METHOD → CALLS → EXTERNAL_CALL
        if external_batch:
            try:
                self.connector.execute_query("""
                    UNWIND $batch AS row
                    MATCH (caller:METHOD {qualname: row.caller_qualname})
                    MERGE (ext:EXTERNAL_CALL {qualname: row.ext_qualname})
                    SET ext.name = row.name,
                        ext.signature = row.signature
                    MERGE (caller)-[:CALLS]->(ext)
                """, {"batch": external_batch})
            except Exception as e:
                logger.error(f"Failed to batch upsert CALLS (external) edges: {e}")

        logger.info(
            f"CALLS edges: {len(resolved_batch)} resolved, "
            f"{len(external_batch)} external"
        )

    # -----------------------------------------------------------------------
    # CALLS 관계 찾기
    # -----------------------------------------------------------------------

    def _resolve_call_target(
        self, caller_qualname: str, target_name: str, obj_name: str,
    ) -> str | None:
        """호출 대상을 인메모리 인덱스로 해석하여 METHOD qualname을 반환합니다."""
        if obj_name:
            # Case 1a: obj_name이 타입명 → 해당 타입의 메서드 탐색
            type_q = self._type_by_name.get(obj_name)
            if type_q:
                methods = self._methods_by_class.get(type_q, {}).get(target_name, [])
                if methods:
                    return methods[0].qualname

            # Case 1b: obj_name이 필드명 → 필드 타입의 메서드 탐색
            caller_method = self._methods.get(caller_qualname)
            if caller_method:
                field = self._fields_by_class.get(
                    caller_method.class_qualname, {},
                ).get(obj_name)
                if field and field.field_type.get("layout"):
                    field_type_name = field.field_type["layout"][0]
                    type_q = self._type_by_name.get(field_type_name)
                    if type_q:
                        methods = self._methods_by_class.get(type_q, {}).get(target_name, [])
                        if methods:
                            return methods[0].qualname
        else:
            # Case 2: obj_name 없음 → 같은 클래스의 형제 메서드 탐색
            caller_method = self._methods.get(caller_qualname)
            if caller_method:
                methods = self._methods_by_class.get(
                    caller_method.class_qualname, {},
                ).get(target_name, [])
                if methods:
                    return methods[0].qualname

        return None

    # -----------------------------------------------------------------------
    # 메모리 정리
    # -----------------------------------------------------------------------

    def _clear(self):
        """메모리 저장소를 초기화합니다."""
        self._types.clear()
        self._fields.clear()
        self._methods.clear()
        self._calls.clear()
        self._param_edges.clear()
        self._return_edges.clear()
