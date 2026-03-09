from neo4j import GraphDatabase
import logging
from config import Config

# 주의: logging.basicConfig()는 앱 진입점(api/main.py)에서 한 번만 호출해야 합니다.
# 모듈 레벨에서 호출하면 다른 모듈의 로깅 설정을 덮어쓸 수 있습니다.
logger = logging.getLogger(__name__)

class DBClient:
    """
    Neo4j 그래프 데이터베이스와의 연결 및 쿼리 실행을 관리하는 클라이언트입니다.
    """
    def __init__(self):
        self.driver = None
        self.connect()

    def connect(self):
        try:
            self.driver = GraphDatabase.driver(
                Config.NEO4J_URI,
                auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD)
            )
            # 연결 테스트
            self.driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {Config.NEO4J_URI}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self):
        if self.driver:
            self.driver.close()

    def execute_query(self, query, parameters=None):
        """Cypher 쿼리를 실행하고 결과를 리스트 형태로 반환합니다."""
        if not self.driver:
            raise ConnectionError("Neo4j driver is not connected")

        clean_query = self._remove_cypher_comments(query)

        try:
            with self.driver.session() as session:
                result = session.run(clean_query, parameters)
                return [record for record in result]
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise

    def clear_database(self):
        """데이터베이스의 모든 노드와 엣지를 삭제합니다. (초기화용)"""
        logger.warning("Clearing entire database...")
        self.execute_query("MATCH (n) DETACH DELETE n")
        logger.info("Database cleared.")

    def create_constraints(self):
        """성능 향상을 위한 인덱스 및 제약 조건 생성"""
        queries = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (f:FILE) REQUIRE f.path IS UNIQUE",
            "CREATE INDEX IF NOT EXISTS FOR (f:FILE) ON (f.name)",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (t:TYPE) REQUIRE t.qualname IS UNIQUE",
            "CREATE INDEX IF NOT EXISTS FOR (t:TYPE) ON (t.name)",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:METHOD) REQUIRE m.qualname IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (f:FIELD) REQUIRE f.qualname IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:EXTERNAL_CALL) REQUIRE e.qualname IS UNIQUE",
        ]
        for q in queries:
            try:
                self.execute_query(q)
            except Exception as e:
                logger.warning(f"Constraint creation warning: {e}")

    def _remove_cypher_comments(self, query: str) -> str:
        """Cypher 쿼리에서 주석을 제거합니다 (쿼리 로그 가독성 향상)."""
        lines = []
        for line in query.split('\n'):
            if '//' in line:
                line = line.split('//')[0]
            if line.strip():
                lines.append(line.rstrip())
        return '\n'.join(lines)
