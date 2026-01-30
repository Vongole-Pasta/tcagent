import os
import hashlib
from typing import List, Dict
from infra.db_client import DBClient
from graph_db.queries import CypherQueries
from config import Config
import logging

logger = logging.getLogger(__name__)

class DiffChecker:
    def __init__(self, connector: DBClient):
        self.connector = connector
        # self.queries = CypherQueries() # Using static class directly or instance? Original used instance
        # In queries.py I defined it as a class with constants. 
        # But commonly used as CypherQueries.GET_FILE_HASH if they are static.
        # Let's check original usage: self.queries.GET_FILE_HASH. 
        # In Step 90, they are class attributes (static). So I can use CypherQueries.QUERY_NAME.

    def detect_changes(self, file_paths: List[str]) -> List[Dict]:
        """
        입력: 절대 경로(또는 프로젝트 루트 상대 경로) 목록
        출력: 변경 상태 메타데이터가 포함된 파일 목록
        """
        changes = []
        for path in file_paths:
            # Ensure path is relative for DB lookup
            rel_path = os.path.relpath(path, Config.TARGET_DIR) if os.path.isabs(path) else path
            abs_path = os.path.join(Config.TARGET_DIR, rel_path)
            
            if not os.path.exists(abs_path):
                logger.warning(f"File not found: {abs_path}")
                continue
                
            current_hash = self._calculate_hash(abs_path)
            stored_hash_record = self.connector.execute_query(CypherQueries.GET_FILE_HASH, {"file_path": rel_path})
            
            is_new = not stored_hash_record
            is_modified = False
            is_relocated = False
            
            if not is_new:
                stored_hash = stored_hash_record[0]['hash']
                if current_hash != stored_hash:
                    is_modified = True
            else:
                # If path is new, check if we have this hash somewhere else (Relocation)
                # We need a query to find file by hash
                existing_hash_node = self.connector.execute_query(
                    "MATCH (f:FILE {hash: $hash}) RETURN f.path as path", 
                    {"hash": current_hash}
                )
                if existing_hash_node:
                    is_relocated = True
                    # Optional: We could store 'old_path' for reference
            
            if is_new or is_modified or is_relocated:
                status = "NEW"
                if is_modified: status = "MODIFIED"
                if is_relocated: status = "RELOCATED"
                
                changes.append({
                    "file_path": rel_path,
                    "absolute_path": abs_path,
                    "status": status,
                    "new_hash": current_hash
                })
        
        return changes

    def _calculate_hash(self, file_path):
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash: {e}")
            return None
