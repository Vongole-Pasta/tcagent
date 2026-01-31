import logging
import os
from infra.db_client import DBClient
from infra.code_loader import CodeLoader
from core.analysis.architecture_builder import ArchitectureBuilder
from core.analysis.flow_builder import FlowBuilder
from config import Config

logger = logging.getLogger(__name__)

class IncrementalAnalyzer:
    def __init__(self, connector: DBClient):
        self.connector = connector
        self.ingestor = CodeLoader(connector)
        self.arch_builder = ArchitectureBuilder(connector)
        self.flow_builder = FlowBuilder(connector)

    def process_files_from_memory(self, files_data: list[dict], project: str = None):
        """
        메모리에 있는 파일들을 직접 처리 (디스크 I/O 없음)
        
        Args:
            files_data: [{"path": "relative/path.java", "content": b"..."}, ...]
            project: 프로젝트 이름
        """
        updated_files = []
        
        if not files_data:
            return []

        # [CRITICAL UPDATE]
        # GraphRag logic normally strips common path (upload_root).
        # However, for tcagent multi-project support in DB, we must ensure UNIQUE paths.
        # If we strip common path, different projects will have same paths (e.g. 'src/main/...') and Collide.
        # So we DISABLE stripping here to simulate distinct folders.
        # Or, we prepend project name if needed. 
        # For now, we use the path AS IS from the ZIP, assuming user zipped the project folder.
        
        # upload_root logic removed/disabled.
        upload_root = '' 
        
        for file_data in files_data:
            file_path = file_data['path']
            content = file_data['content']
            
            logger.info(f"Processing {file_path} from memory")
            
            try:
                # 1. Create FILE node (without disk file)
                file_hash = self.ingestor.calculate_file_hash_from_content(content)
                # Ensure path is unique by prepending project if it's not already in path
                # But to follow GraphRag strictly, we just use the path.
                # If user zips 'src/...', path is 'src/...'.
                
                relative_path = file_path # No stripping
                file_name = os.path.basename(file_path)
                
                # Determine language
                ext = os.path.splitext(file_name)[1]
                language = Config.ALLOWED_EXTENSIONS.get(ext, "UNKNOWN")
                
                query = """
                MERGE (f:FILE {path: $path, project: $project})
                SET f.name = $name,
                    f.hash = $hash,
                    f.language = $language
                """
                
                self.connector.execute_query(query, {
                    "path": relative_path,
                    "name": file_name,
                    "hash": file_hash,
                    "language": language,
                    "project": project
                })
                
                # 2. Architecture Analysis from memory
                # GraphRag Builders DO NOT ingest project! They rely on file path unique match.
                self.arch_builder.process_file_from_content(relative_path, content)
                
                # 3. Flow Analysis from memory
                self.flow_builder.process_file_from_content(relative_path, content)
                
                updated_files.append(relative_path)
                logger.info(f"Completed analysis for {file_path} from memory")
                
            except Exception as e:
                logger.error(f"Failed to process {file_path} from memory: {e}")
        
        # 4. Global Resolution
        if updated_files:
            logger.info("Re-resolving global call topology...")
            self.flow_builder._resolve_calls()
            
        return updated_files
