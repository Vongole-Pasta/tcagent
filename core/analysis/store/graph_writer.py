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

    def flush(self, registry: ParsedRegistry):
        """ParsedRegistry의 노드와 해석된 엣지(resolved)를 일괄 DB에 기록합니다."""
        resolved = registry.resolved
        logger.info(
            f"Flushing to DB: {len(registry.types)} types, "
            f"{len(registry.fields)} fields, {len(registry.methods)} methods, "
            f"{len(resolved.internal_calls) + len(resolved.external_calls)} calls, "
            f"{len(resolved.params)} params, {len(resolved.returns)} returns"
        )

        # ── 노드 저장 ──
        self._flush_types(registry.types)
        self._flush_fields(registry.fields)
        self._flush_methods(registry.methods)

        # ── 엣지 저장 ──
        self._flush_parameter_edges(resolved.params)
        self._flush_return_edges(resolved.returns)
        self._flush_calls(resolved.internal_calls, resolved.external_calls)

        logger.info("Flush complete.")

    # -----------------------------------------------------------------------
    # 노드 Flush
    # -----------------------------------------------------------------------

    def _flush_types(self, types: dict[str, ParsedType]):
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

    def _flush_fields(self, fields: dict[str, ParsedField]):
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

    def _flush_methods(self, methods: dict[str, ParsedMethod]):
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
    # 엣지 Flush (UNWIND 배치)
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

    def _flush_calls(self, resolved_batch: list[dict], external_batch: list[dict]):
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
