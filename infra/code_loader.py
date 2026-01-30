import os
import hashlib
from config import Config
from infra.db_client import DBClient
import logging

logger = logging.getLogger(__name__)

class CodeLoader:
    def __init__(self, connector: DBClient):
        self.connector = connector

    def calculate_file_hash(self, file_path):
        """
        파일 내용의 SHA-256 해시를 계산합니다.
        대용량 파일 처리를 위해 청크 단위로 읽습니다.
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
        메모리에 있는 파일 내용의 SHA-256 해시를 계산합니다.
        """
        sha256_hash = hashlib.sha256()
        sha256_hash.update(content)
        return sha256_hash.hexdigest()

    def ingest_directory(self, root_dir=None):
        """
        지정된 디렉토리를 재귀적으로 탐색하여 FILE 노드를 생성합니다.
        설정된 제외(Excluded) 폴더와 허용(Allowed) 확장자를 따릅니다.
        """
        if root_dir is None:
            root_dir = Config.TARGET_DIR

        logger.info(f"Starting ingestion for directory: {root_dir}")
        count = 0
        
        for root, dirs, files in os.walk(root_dir):
            # 제외할 디렉토리 건너뛰기
            dirs[:] = [d for d in dirs if d not in Config.EXCLUDED_DIRS]
            
            for file in files:
                file_path = os.path.join(root, file)
                _, ext = os.path.splitext(file)
                
                # 허용된 확장자(Java)만 처리
                if ext in Config.ALLOWED_EXTENSIONS:
                    self.ingest_file(file_path, root_dir)
                    count += 1
        
        logger.info(f"Ingestion completed. Processed {count} files.")

    def ingest_file(self, file_path, root_dir, project=None):
        """
        개별 파일에 대한 메타데이터(경로, 언어, 해시)를 파싱하여 DB에 FILE 노드로 저장합니다.
        Project 파라미터가 있으면 해당 프로젝트 태그를 추가합니다.
        """
        file_hash = self.calculate_file_hash(file_path)
        # DB에는 상대 경로(식별자) 저장, 파일 읽기는 절대 경로 사용
        relative_path = os.path.relpath(file_path, root_dir)
        file_name = os.path.basename(file_path)
        
        # 언어 식별
        language = "UNKNOWN"
        ext = os.path.splitext(file_name)[1]
        
        # Java Only check
        if ext == ".java":
            language = "JAVA"
        else:
            # Should be handled by caller, but safe check here
            return 

        query = """
        MERGE (f:FILE {path: $path, project: $project})
        SET f.name = $name,
            f.hash = $hash,
            f.language = $language

        """
        
        parameters = {
            "path": relative_path,
            "name": file_name,
            "hash": file_hash,
            "language": language,
            "project": project
        }
        
        try:
            self.connector.execute_query(query, parameters)
            logger.debug(f"Ingested file: {relative_path}")
        except Exception as e:
            logger.error(f"Failed to ingest file {file_path}: {e}")
