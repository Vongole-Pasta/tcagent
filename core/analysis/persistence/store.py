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
    ParsedType, ParsedField, ParsedFileResult,
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

        # --- 메모리 저장소 ---
        self._types: dict[str, ParsedType] = {}         # qualname → ParsedType
        self._fields: dict[str, ParsedField] = {}       # qualname → ParsedField

    # -----------------------------------------------------------------------
    # 수집 (DB 접근 없음)
    # -----------------------------------------------------------------------

    def collect(self, result: ParsedFileResult):
        """파싱 결과를 메모리에 축적합니다. DB 접근 없음."""
        for t in result.types:
            self._types[t.qualname] = t
        for f in result.fields:
            self._fields[f.qualname] = f

    # -----------------------------------------------------------------------
    # 일괄 기록
    # -----------------------------------------------------------------------

    def flush(self):
        """메모리에 축적된 전체 데이터를 일괄 DB에 기록합니다."""
        logger.info(f"Flushing to DB: {len(self._types)} types, {len(self._fields)} fields")

        # 1단계: 노드 생성
        self._flush_types()
        self._flush_fields()

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

    # -----------------------------------------------------------------------
    # 개별 Upsert
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

    # -----------------------------------------------------------------------
    # 메모리 정리
    # -----------------------------------------------------------------------

    def _clear(self):
        """메모리 저장소를 초기화합니다."""
        self._types.clear()
        self._fields.clear()
