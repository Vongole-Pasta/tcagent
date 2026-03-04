import logging

from graph_db.client import DBClient
from core.analysis.lang import PARSERS
from core.analysis.persistence.store import GraphWriter

logger = logging.getLogger(__name__)


class Builder:
    """
    [플로우 빌더]
    메서드 레벨의 상세 분석(Flow Analysis)을 담당합니다.
    각 파일의 메서드를 추출(Method Node)하고, 메서드 간의 호출 관계(Call Relationship)를 연결합니다.

    사용 흐름:
      1. process_file_from_content()  — 파일별 파싱 + 메모리 축적 (DB 접근 없음)
      2. flush()                      — 축적된 전체 데이터를 일괄 DB 기록 + 엣지 해석
    """
    def __init__(self, connector: DBClient):
        self.connector = connector
        self.parsers = PARSERS
        self.writer = GraphWriter(connector)

    def process_file_from_content(self, file_path: str, content: bytes, language: str, scan_id: str | None = None):
        """
        [메모리 기반 플로우 분석]
        파일 내용을 파싱하여 결과를 메모리에 축적합니다. DB 접근 없음.

        Args:
            file_path: 파일 경로
            content: 파일 내용
            language: 언어명 (예: "java")
            scan_id: 스마트 업데이트용 스캔 ID
        """
        lang_parser = self.parsers.get(language)
        if not lang_parser:
            return

        try:
            result = lang_parser.parse(content, file_path, scan_id)
            self.writer.collect(result)

        except Exception as e:
            logger.error(f"Failed to process flow for {file_path}: {e}")

    def flush(self):
        """축적된 전체 데이터를 일괄 DB에 기록합니다."""
        self.writer.flush()

    def prune_nodes(self, file_path: str, scan_id: str):
        """
        [메서드 가지치기 (Pruning)]
        Smart Update의 후처리 단계입니다.
        이번 스캔(scan_id)에서 발견되지 않은 메서드는 소스 코드에서 삭제된 것으로 간주합니다.
        해당 메서드를 'DELETED'로 마킹하고, 다른 메서드와의 호출 관계(Flow)를 끊어냅니다.
        """
        query = """
        MATCH (f:FILE {path: $file_path})
        MATCH (f)-[:CONTAINS*1..3]->(m:METHOD)

        WHERE m.last_scan_id <> $scan_id

        // Mark as DELETED
        SET m.status = 'DELETED'

        WITH m
        // [격리] 다른 메서드와의 호출 관계 제거 (분석 방해 방지)
        OPTIONAL MATCH (m)-[r:CALLS]-()
        DELETE r
        """
        try:
            self.connector.execute_query(query, {"file_path": file_path, "scan_id": scan_id})
            logger.info(f"Marked stale methods as DELETED for {file_path} (ScanID: {scan_id})")
        except Exception as e:
            logger.error(f"Pruning Error ({file_path}): {e}")
