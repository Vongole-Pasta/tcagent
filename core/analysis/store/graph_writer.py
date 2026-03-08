"""
파싱 결과를 Neo4j에 영속화하는 모듈 (Memory-First).

모든 파일의 파싱 결과를 메모리에 축적한 뒤,
EdgeLinker로 관계를 해석하고, 일괄로 DB에 기록합니다.
UNWIND 배치 쿼리로 DB 라운드트립을 최소화하여 대규모 소스코드도 효율적으로 처리합니다.
"""
import json
import logging
from dataclasses import asdict

from graph_db.client import DBClient
from graph_db.queries import CypherQueries

from .models import (
    ParsedType, ParsedField, ParsedMethod, ParsedFileResult,
    ParsedCallEdge, ParsedParameterEdge, ParsedReturnEdge,
)
from .edge_linker import EdgeLinker

logger = logging.getLogger(__name__)


class GraphWriter:
    """
    [그래프 DB 라이터 — Memory-First 방식]

    사용 흐름:
      1. collect(result)  — 파일별 파싱 결과를 메모리에 축적 (DB 접근 없음)
      2. flush()          — 축적된 전체 데이터를 일괄 DB 기록

    모든 노드가 메모리에 존재하는 상태에서 EdgeLinker가 관계를 해석하므로,
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

        # 2단계: 엣지 해석 (EdgeLinker — 순수 인메모리)
        linker = EdgeLinker(self._types, self._fields, self._methods)

        # 3단계: 엣지 생성
        self._flush_parameter_edges(linker)
        self._flush_return_edges(linker)
        self._flush_calls(linker)

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
            self.connector.execute_query(
                CypherQueries.BATCH_UPSERT_TYPES, {"batch": batch}
            )
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
            self.connector.execute_query(
                CypherQueries.BATCH_UPSERT_FIELDS, {"batch": batch}
            )
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
            self.connector.execute_query(
                CypherQueries.BATCH_UPSERT_METHODS, {"batch": batch}
            )
        except Exception as e:
            logger.error(f"Failed to batch upsert METHODs: {e}")

    # -----------------------------------------------------------------------
    # 엣지 Flush (UNWIND 배치)
    # -----------------------------------------------------------------------

    def _flush_parameter_edges(self, linker: EdgeLinker):
        """HAS_PARAMETER 엣지를 DB에 기록합니다. 해석은 EdgeLinker가 담당."""
        batch = linker.resolve_parameter_edges(self._param_edges)
        if not batch:
            return

        try:
            self.connector.execute_query(
                CypherQueries.BATCH_UPSERT_PARAMETER_EDGES, {"batch": batch}
            )
        except Exception as e:
            logger.error(f"Failed to batch upsert HAS_PARAMETER edges: {e}")

    def _flush_return_edges(self, linker: EdgeLinker):
        """RETURNS 엣지를 DB에 기록합니다. 해석은 EdgeLinker가 담당."""
        batch = linker.resolve_return_edges(self._return_edges)
        if not batch:
            return

        try:
            self.connector.execute_query(
                CypherQueries.BATCH_UPSERT_RETURN_EDGES, {"batch": batch}
            )
        except Exception as e:
            logger.error(f"Failed to batch upsert RETURNS edges: {e}")

    def _flush_calls(self, linker: EdgeLinker):
        """CALLS 엣지를 DB에 기록합니다. 해석은 EdgeLinker가 담당."""
        resolved_batch, external_batch = linker.resolve_calls(self._calls)

        # resolved: METHOD → CALLS → METHOD
        if resolved_batch:
            try:
                self.connector.execute_query(
                    CypherQueries.BATCH_UPSERT_CALLS, {"batch": resolved_batch}
                )
            except Exception as e:
                logger.error(f"Failed to batch upsert CALLS (resolved) edges: {e}")

        # external: METHOD → CALLS → EXTERNAL_CALL
        if external_batch:
            try:
                self.connector.execute_query(
                    CypherQueries.BATCH_UPSERT_EXTERNAL_CALLS, {"batch": external_batch}
                )
            except Exception as e:
                logger.error(f"Failed to batch upsert CALLS (external) edges: {e}")

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
