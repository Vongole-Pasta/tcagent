"""
파싱 결과를 Neo4j에 영속화하는 모듈 (Stateless).

외부에서 전달받은 ParsedRegistry(등록소)를
UNWIND 배치 쿼리로 일괄 DB에 기록합니다.
메모리 저장소를 갖지 않으므로, 싱글톤으로 사용해도 동시접속에 안전합니다.
"""
import json
import logging
from dataclasses import asdict

from graph_db.client import DBClient
from graph_db.queries import CypherQueries

from .models import ParsedType, ParsedField, ParsedMethod, ParsedRegistry

logger = logging.getLogger(__name__)


class GraphWriter:
    """
    [그래프 DB 라이터 — Stateless]

    외부에서 전달받은 ParsedRegistry를 DB에 기록만 합니다.
    메모리 저장소를 갖지 않으므로, 싱글톤으로 사용해도 동시접속에 안전합니다.
    """

    def __init__(self, connector: DBClient):
        self.connector = connector

    # -----------------------------------------------------------------------
    # 일괄 기록 (UNWIND 배치)
    # -----------------------------------------------------------------------

    def write(self, registry: ParsedRegistry, changed: list[dict] = None,
              unchanged: list[str] = None, project: str = None):
        """
        분석 결과를 일괄 DB에 기록합니다.

        실행 순서 (의존성 기반):
            1. AS-IS status — 변경 없는 메서드의 status를 'AS-IS'로 갱신
            2. FILE 노드    — 모든 FILE 노드 기록
            3. 노드 (dirty)  — NEW/MODIFIED 파일의 TYPE/FIELD/METHOD만 기록
            4. 구조 엣지     — CONTAINS (FILE→TYPE, TYPE→FIELD, TYPE→METHOD, FIELD→TYPE)
            5. 의미 엣지     — CALLS, HAS_PARAMETER, RETURNS

        증분 분석 최적화:
            dirty set에 포함된 노드(NEW/MODIFIED)만 기록합니다.
            AS-IS 노드는 DB에 이미 존재하므로 재기록 불필요.
        """
        resolved = registry.resolved

        # ── 1. 변경 없는 메서드 status 갱신 (대시보드 표시용) ──
        self._update_asis_status(unchanged, project)

        # ── 2. FILE 노드 저장 ──
        if changed:
            self._flush_file_nodes(changed)

        # ── 3. 노드 저장 (변경분만) ──
        dirty_types = {qn: t for qn, t in registry.types.items() if qn in registry.dirty_types}
        dirty_fields = {qn: f for qn, f in registry.fields.items() if qn in registry.dirty_fields}
        dirty_methods = {qn: m for qn, m in registry.methods.items() if qn in registry.dirty_methods}

        logger.info(
            f"Writing to DB: {len(unchanged or [])} unchanged, {len(changed or [])} changed, "
            f"{len(dirty_types)} type nodes, {len(dirty_fields)} field nodes, "
            f"{len(dirty_methods)} method nodes, "
            f"{len(resolved.internal_calls_edges) + len(resolved.external_calls_edges)} calls edges, "
            f"{len(resolved.has_parameter_edges)} has_parameter edges, {len(resolved.returns_edges)} returns edges, "
            f"{len(resolved.contains_edges)} field → type contains"
        )

        self._flush_type_nodes(dirty_types)
        self._flush_field_nodes(dirty_fields)
        self._flush_method_nodes(dirty_methods)

        # ── 4. 구조 엣지 (CONTAINS 4종) ──
        self._flush_contains_edges(dirty_types, dirty_fields, dirty_methods, resolved.contains_edges)

        # ── 5. 의미 엣지 ──
        self._flush_parameter_edges(resolved.has_parameter_edges)
        self._flush_return_edges(resolved.returns_edges)
        self._flush_calls_edges(resolved.internal_calls_edges, resolved.external_calls_edges)

        logger.info("Write complete.")

    # -----------------------------------------------------------------------
    # FILE Flush
    # -----------------------------------------------------------------------

    def _flush_file_nodes(self, batch: list[dict]):
        """FILE 노드를 UNWIND 배치로 일괄 DB에 기록합니다."""
        try:
            self.connector.execute_query(
                CypherQueries.BATCH_UPSERT_FILES, {"batch": batch}
            )
        except Exception as e:
            logger.error(f"Failed to batch upsert FILEs: {e}")

    # -----------------------------------------------------------------------
    # 노드 Flush
    # -----------------------------------------------------------------------

    def _flush_type_nodes(self, types: dict[str, ParsedType]):
        """TYPE 노드를 UNWIND 배치로 일괄 DB에 기록합니다."""
        if not types:
            return

        batch = []
        for t in types.values():
            row = asdict(t)
            # list[ConstantInfo] → JSON 문자열
            row["constants"] = json.dumps(row["constants"], ensure_ascii=False) if row["constants"] else ""
            batch.append(row)

        try:
            self.connector.execute_query(
                CypherQueries.BATCH_UPSERT_TYPES, {"batch": batch}
            )
        except Exception as e:
            logger.error(f"Failed to batch upsert TYPEs: {e}")

    def _flush_field_nodes(self, fields: dict[str, ParsedField]):
        """FIELD 노드를 UNWIND 배치로 일괄 DB에 기록합니다."""
        if not fields:
            return

        batch = []
        for f in fields.values():
            row = asdict(f)
            # TypeInfo → JSON 문자열, 키명을 DB 스키마에 맞춤 (field_type → type)
            row["type"] = json.dumps(row.pop("field_type"), ensure_ascii=False)
            batch.append(row)

        try:
            self.connector.execute_query(
                CypherQueries.BATCH_UPSERT_FIELDS, {"batch": batch}
            )
        except Exception as e:
            logger.error(f"Failed to batch upsert FIELDs: {e}")

    def _flush_method_nodes(self, methods: dict[str, ParsedMethod]):
        """METHOD 노드를 UNWIND 배치로 일괄 DB에 기록합니다."""
        if not methods:
            return

        batch = []
        for m in methods.values():
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
            self.connector.execute_query(
                CypherQueries.BATCH_UPSERT_METHODS, {"batch": batch}
            )
        except Exception as e:
            logger.error(f"Failed to batch upsert METHODs: {e}")

    # -----------------------------------------------------------------------
    # 구조 엣지 Flush (CONTAINS 4종)
    # -----------------------------------------------------------------------

    def _flush_contains_edges(self, types: dict[str, ParsedType],
                              fields: dict[str, ParsedField],
                              methods: dict[str, ParsedMethod],
                              field_type_edges: list[dict]):
        """CONTAINS 구조 엣지 4종을 DB에 기록합니다."""
        self._flush_file_contains_type_edges(types)
        self._flush_type_contains_field_edges(fields)
        self._flush_type_contains_method_edges(methods)
        self._flush_field_contains_type_edges(field_type_edges)

    def _flush_file_contains_type_edges(self, types: dict[str, ParsedType]):
        """FILE→CONTAINS→TYPE 엣지를 DB에 기록합니다."""
        if not types:
            return
        batch = [{"file_path": t.file_path, "qualname": t.qualname} for t in types.values()]
        try:
            self.connector.execute_query(
                CypherQueries.BATCH_UPSERT_FILE_CONTAINS_TYPE, {"batch": batch}
            )
        except Exception as e:
            logger.error(f"Failed to flush FILE→CONTAINS→TYPE: {e}")

    def _flush_type_contains_field_edges(self, fields: dict[str, ParsedField]):
        """TYPE→CONTAINS→FIELD 엣지를 DB에 기록합니다."""
        if not fields:
            return
        batch = [{"type_qualname": f.type_qualname, "qualname": f.qualname} for f in fields.values()]
        try:
            self.connector.execute_query(
                CypherQueries.BATCH_UPSERT_TYPE_CONTAINS_FIELD, {"batch": batch}
            )
        except Exception as e:
            logger.error(f"Failed to flush TYPE→CONTAINS→FIELD: {e}")

    def _flush_type_contains_method_edges(self, methods: dict[str, ParsedMethod]):
        """TYPE→CONTAINS→METHOD 엣지를 DB에 기록합니다."""
        if not methods:
            return
        batch = [{"class_qualname": m.class_qualname, "qualname": m.qualname} for m in methods.values()]
        try:
            self.connector.execute_query(
                CypherQueries.BATCH_UPSERT_TYPE_CONTAINS_METHOD, {"batch": batch}
            )
        except Exception as e:
            logger.error(f"Failed to flush TYPE→CONTAINS→METHOD: {e}")

    def _flush_field_contains_type_edges(self, batch: list[dict]):
        """FIELD→CONTAINS→TYPE 엣지를 DB에 기록합니다."""
        if not batch:
            return
        try:
            self.connector.execute_query(
                CypherQueries.BATCH_UPSERT_FIELD_CONTAINS_TYPE, {"batch": batch}
            )
        except Exception as e:
            logger.error(f"Failed to flush FIELD→CONTAINS→TYPE: {e}")

    # -----------------------------------------------------------------------
    # 의미 엣지 Flush (UNWIND 배치)
    # -----------------------------------------------------------------------

    def _flush_parameter_edges(self, batch: list[dict]):
        """HAS_PARAMETER 엣지를 DB에 기록합니다."""
        if not batch:
            return
        try:
            self.connector.execute_query(
                CypherQueries.BATCH_UPSERT_PARAMETER_EDGES, {"batch": batch}
            )
        except Exception as e:
            logger.error(f"Failed to batch upsert HAS_PARAMETER edges: {e}")

    def _flush_return_edges(self, batch: list[dict]):
        """RETURNS 엣지를 DB에 기록합니다."""
        if not batch:
            return
        try:
            self.connector.execute_query(
                CypherQueries.BATCH_UPSERT_RETURN_EDGES, {"batch": batch}
            )
        except Exception as e:
            logger.error(f"Failed to batch upsert RETURNS edges: {e}")

    def _flush_calls_edges(self, resolved_batch: list[dict], external_batch: list[dict]):
        """CALLS 엣지를 DB에 기록합니다."""
        if resolved_batch:
            try:
                self.connector.execute_query(
                    CypherQueries.BATCH_UPSERT_CALLS, {"batch": resolved_batch}
                )
            except Exception as e:
                logger.error(f"Failed to batch upsert CALLS (resolved) edges: {e}")

        if external_batch:
            try:
                self.connector.execute_query(
                    CypherQueries.BATCH_UPSERT_EXTERNAL_CALLS, {"batch": external_batch}
                )
            except Exception as e:
                logger.error(f"Failed to batch upsert CALLS (external) edges: {e}")

    # -----------------------------------------------------------------------
    # 후처리 (write 이후 호출)
    # -----------------------------------------------------------------------

    def prune_removed_methods(self, batch: list[dict]):
        """
        변경 파일에서 삭제된 메서드를 DELETED 마킹하고 CALLS를 끊습니다.

        write() 이후에 호출해야 합니다:
            METHOD UPSERT로 scan_id가 갱신된 뒤 실행해야,
            현존 메서드가 삭제된 것으로 오인되지 않습니다.
        """
        if not batch:
            return
        try:
            self.connector.execute_query(
                CypherQueries.BATCH_PRUNE_STALE_METHODS, {"batch": batch}
            )
        except Exception as e:
            logger.error(f"Failed to prune removed methods: {e}")

    def _update_asis_status(self, unchanged: list[str], project: str):
        """변경 없는 파일의 METHOD 노드 status를 'AS-IS'로 갱신합니다."""
        if not unchanged:
            return
        try:
            self.connector.execute_query(
                CypherQueries.BATCH_UPDATE_ASIS_METHOD_STATUS,
                {"paths": unchanged, "project": project}
            )
        except Exception as e:
            logger.error(f"Failed to update AS-IS method status: {e}")
