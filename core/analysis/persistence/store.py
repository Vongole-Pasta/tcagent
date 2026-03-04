"""
파싱 결과를 Neo4j에 영속화하는 모듈 (Memory-First).

모든 파일의 파싱 결과를 메모리에 축적한 뒤,
관계 해석까지 완료한 후 일괄로 DB에 기록합니다.
DB 라운드트립을 최소화하여 대규모 소스코드(~3GB)도 효율적으로 처리합니다.
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
    # 일괄 기록
    # -----------------------------------------------------------------------

    def flush(self):
        """메모리에 축적된 전체 데이터를 일괄 DB에 기록합니다."""
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

    def _flush_types(self):
        """축적된 TYPE 노드를 일괄 DB에 기록합니다."""
        for t in self._types.values():
            self._upsert_type(t)

    def _flush_fields(self):
        """축적된 FIELD 노드를 일괄 DB에 기록합니다."""
        for f in self._fields.values():
            self._upsert_field(f)

    def _flush_methods(self):
        """축적된 METHOD 노드를 일괄 DB에 기록합니다."""
        for m in self._methods.values():
            self._upsert_method(m)

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
    # 엣지 Flush
    # -----------------------------------------------------------------------

    def _flush_parameter_edges(self):
        """HAS_PARAMETER 엣지를 DB에 기록합니다. METHOD → HAS_PARAMETER → TYPE."""
        for edge in self._param_edges:
            for type_name in edge.param_info["type"]["layout"]:
                type_qualname = self._type_by_name.get(type_name)
                if type_qualname:
                    self._upsert_has_parameter(edge, type_qualname)

    def _flush_return_edges(self):
        """RETURNS 엣지를 DB에 기록합니다. METHOD → RETURNS → TYPE."""
        for edge in self._return_edges:
            for type_name in edge.return_info["layout"]:
                type_qualname = self._type_by_name.get(type_name)
                if type_qualname:
                    self._upsert_returns(edge, type_qualname)

    def _flush_calls(self):
        """CALLS 엣지를 해석하고 DB에 기록합니다."""
        resolved, external = 0, 0
        for call in self._calls:
            target_qualname = self._resolve_call_target(
                call.caller_qualname, call.target_method_name, call.object_name,
            )
            if target_qualname:
                self._upsert_calls_method(call, target_qualname)
                resolved += 1
            else:
                self._upsert_calls_external(call)
                external += 1
        logger.info(f"CALLS edges: {resolved} resolved, {external} external")

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
    # 개별 Upsert — 노드
    # -----------------------------------------------------------------------

    def _upsert_type(self, parsed: ParsedType):
        """TYPE 노드 upsert + FILE→CONTAINS→TYPE 관계 연결."""
        try:
            params = asdict(parsed)
            # list[ConstantInfo] → JSON 문자열로 직렬화
            params["constants"] = json.dumps(params["constants"], ensure_ascii=False) if params["constants"] else ""

            self.connector.execute_query("""
                // qualname을 PK로 사용하여 TYPE 노드를 생성하거나 갱신합니다.
                MERGE (t:TYPE {qualname: $qualname})
                SET t.name = $name,
                    t.kind = $kind,
                    t.constants = $constants

                // 해당 TYPE이 속한 FILE과 CONTAINS 관계를 연결합니다.
                WITH t
                MATCH (f:FILE {path: $file_path})
                MERGE (f)-[:CONTAINS]->(t)
            """, params)
        except Exception as e:
            logger.error(f"Failed to upsert TYPE {parsed.qualname}: {e}")

    def _upsert_field(self, parsed: ParsedField):
        """FIELD 노드 upsert + TYPE→CONTAINS→FIELD 관계 연결."""
        try:
            params = asdict(parsed)
            # TypeInfo → JSON 문자열로 직렬화, 키명을 DB 스키마에 맞춤 (field_type → type)
            params["type"] = json.dumps(params.pop("field_type"), ensure_ascii=False)

            self.connector.execute_query("""
                // qualname을 PK로 사용하여 FIELD 노드를 생성하거나 갱신합니다.
                MERGE (f:FIELD {qualname: $qualname})
                SET f.name = $name,
                    f.type = $type,
                    f.constraint = $constraint

                // 해당 FIELD가 속한 TYPE과 CONTAINS 관계를 연결합니다.
                WITH f
                MATCH (t:TYPE {qualname: $type_qualname})
                MERGE (t)-[:CONTAINS]->(f)
            """, params)
        except Exception as e:
            logger.error(f"Failed to upsert FIELD {parsed.qualname}: {e}")

    def _upsert_method(self, parsed: ParsedMethod):
        """METHOD 노드 upsert + TYPE→CONTAINS→METHOD 관계 연결."""
        try:
            params = asdict(parsed)
            # list[ParamInfo] → JSON 문자열로 직렬화
            params["params"] = json.dumps(params["params"], ensure_ascii=False)
            # TypeInfo|None → JSON 문자열로 직렬화
            params["return_type"] = json.dumps(params["return_type"], ensure_ascii=False) if params["return_type"] else ""
            # 키명을 DB 스키마에 맞춤 (method_hash → hash, scan_id → last_scan_id)
            params["hash"] = params.pop("method_hash")
            params["last_scan_id"] = params.pop("scan_id") or ""

            self.connector.execute_query("""
                // qualname을 PK로 사용하여 METHOD 노드를 생성하거나 갱신합니다.
                // status: NEW(신규생성), MODIFIED(변경됨), AS-IS(동일)
                MERGE (m:METHOD {qualname: $qualname})
                ON CREATE SET m.status = 'NEW'
                ON MATCH SET m.status = CASE
                    WHEN m.hash = $hash THEN 'AS-IS'
                    ELSE 'MODIFIED'
                END

                SET m.name = $name,
                    m.signature = $signature,
                    m.source = $source,
                    m.hash = $hash,
                    m.params = $params,
                    m.return_type = $return_type,
                    m.endpoint_uri = $endpoint_uri,
                    m.http_method = $http_method,
                    m.last_scan_id = $last_scan_id

                // 해당 METHOD가 속한 TYPE과 CONTAINS 관계를 연결합니다.
                WITH m
                MATCH (t:TYPE {qualname: $class_qualname})
                MERGE (t)-[:CONTAINS]->(m)
            """, params)
        except Exception as e:
            logger.error(f"Failed to upsert METHOD {parsed.qualname}: {e}")

    # -----------------------------------------------------------------------
    # 개별 Upsert — 엣지
    # -----------------------------------------------------------------------

    def _upsert_has_parameter(self, parsed: ParsedParameterEdge, type_qualname: str):
        """METHOD → HAS_PARAMETER → TYPE 엣지를 DB에 기록합니다."""
        try:
            params = asdict(parsed)
            params["type_qualname"] = type_qualname

            self.connector.execute_query("""
                MATCH (m:METHOD {qualname: $method_qualname})
                MATCH (t:TYPE {qualname: $type_qualname})
                MERGE (m)-[:HAS_PARAMETER]->(t)
            """, params)
        except Exception as e:
            logger.error(f"Failed to upsert HAS_PARAMETER {parsed.method_qualname} → {type_qualname}: {e}")

    def _upsert_returns(self, parsed: ParsedReturnEdge, type_qualname: str):
        """METHOD → RETURNS → TYPE 엣지를 DB에 기록합니다."""
        try:
            params = asdict(parsed)
            params["type_qualname"] = type_qualname

            self.connector.execute_query("""
                MATCH (m:METHOD {qualname: $method_qualname})
                MATCH (t:TYPE {qualname: $type_qualname})
                MERGE (m)-[:RETURNS]->(t)
            """, params)
        except Exception as e:
            logger.error(f"Failed to upsert RETURNS {parsed.method_qualname} → {type_qualname}: {e}")

    def _upsert_calls_method(self, parsed: ParsedCallEdge, callee_qualname: str):
        """METHOD → CALLS → METHOD 엣지를 DB에 기록합니다."""
        try:
            params = asdict(parsed)
            params["callee_qualname"] = callee_qualname

            self.connector.execute_query("""
                MATCH (caller:METHOD {qualname: $caller_qualname})
                MATCH (callee:METHOD {qualname: $callee_qualname})
                MERGE (caller)-[:CALLS]->(callee)
            """, params)
        except Exception as e:
            logger.error(f"Failed to upsert CALLS {parsed.caller_qualname} → {callee_qualname}: {e}")

    def _upsert_calls_external(self, parsed: ParsedCallEdge):
        """METHOD → CALLS → EXTERNAL_CALL 엣지를 DB에 기록합니다."""
        try:
            params = asdict(parsed)
            # 키명을 DB 스키마에 맞춤
            params["ext_qualname"] = f"{parsed.object_name}.{parsed.target_method_name}" if parsed.object_name else parsed.target_method_name
            params["name"] = parsed.target_method_name
            params["signature"] = f"{params['ext_qualname']}()"

            self.connector.execute_query("""
                MATCH (caller:METHOD {qualname: $caller_qualname})
                MERGE (ext:EXTERNAL_CALL {qualname: $ext_qualname})
                SET ext.name = $name,
                    ext.signature = $signature
                MERGE (caller)-[:CALLS]->(ext)
            """, params)
        except Exception as e:
            logger.error(f"Failed to upsert EXTERNAL_CALL {parsed.caller_qualname} → {parsed.target_method_name}: {e}")

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
