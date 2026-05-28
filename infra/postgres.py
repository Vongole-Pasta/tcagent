import psycopg
from psycopg.rows import dict_row
import logging
from config import Config

logger = logging.getLogger(__name__)

class PostgresClient:
    """
    PostgreSQL 데이터베이스와의 연결 및 쿼리 실행을 관리하는 클라이언트입니다.
    """
    def __init__(self):
        self.conn_info = f"host={Config.POSTGRES_HOST} port={Config.POSTGRES_PORT} dbname={Config.POSTGRES_DB} user={Config.POSTGRES_USER} password={Config.POSTGRES_PASSWORD}"
        self.conn = None
        self.connect()

    def connect(self):
        try:
            self.conn = psycopg.connect(self.conn_info, row_factory=dict_row)
            logger.info(f"Connected to PostgreSQL at {Config.POSTGRES_HOST}:{Config.POSTGRES_PORT}")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()
            logger.info("Closed PostgreSQL connection")

    def execute_query(self, query, parameters=None):
        """SQL 쿼리를 실행하고 결과를 리스트 형태로 반환합니다."""
        if not self.conn or self.conn.closed:
            self.connect()

        try:
            with self.conn.cursor() as cur:
                cur.execute(query, parameters or [])
                res = cur.fetchall() if cur.description else []
                self.conn.commit()
                return res
        except Exception as e:
            if self.conn and not self.conn.closed:
                self.conn.rollback()
            logger.error(f"PostgreSQL Query execution failed: {e}")
            raise


