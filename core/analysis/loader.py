
import hashlib
from infra.db_client import DBClient
import logging

logger = logging.getLogger(__name__)

class Loader:
    """
    파일의 해시 값을 계산하여 변경 사항을 감지하는 유틸리티 클래스입니다.
    과거에는 파일 적재 기능도 담당했으나, 현재는 순수하게 해시 계산 역할만 수행합니다.
    """
    def __init__(self, connector: DBClient):
        self.connector = connector

    def calculate_file_hash(self, file_path):
        """
        [파일 해시 계산]
        디스크에 있는 파일의 내용을 읽어 SHA-256 해시를 계산합니다.
        대용량 파일 처리를 위해 4KB 단위(청크)로 읽어서 메모리 사용을 최적화합니다.
        
        Args:
            file_path (str): 해시를 계산할 파일의 절대 경로
            
        Returns:
            str: 계산된 SHA-256 16진수 문자열 (실패 시 None)
        """
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                # 4K 청크 단위로 읽어서 해시 업데이트
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return None

    def calculate_file_hash_from_content(self, content: bytes):
        """
        [메모리 콘텐츠 해시 계산]
        메모리에 로드된 바이트 데이터(content)의 SHA-256 해시를 계산합니다.
        ZIP 파일 업로드 등 디스크를 거치지 않는 분석 시 사용됩니다.
        
        Args:
            content (bytes): 파일의 바이너리 데이터
            
        Returns:
            str: 계산된 SHA-256 16진수 문자열
        """
        sha256_hash = hashlib.sha256()
        sha256_hash.update(content)
        return sha256_hash.hexdigest()
