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
        
        # Calculate common root from file paths
        if files_data:
            paths = [f['path'] for f in files_data]
            if len(paths) > 1:
                # Find common prefix
                common_parts = []
                first_parts = paths[0].split('/')
                for i, part in enumerate(first_parts):
                    if all(p.split('/')[i] == part if i < len(p.split('/')) else False for p in paths):
                        common_parts.append(part)
                    else:
                        break
                upload_root = '/'.join(common_parts) if common_parts else ''
            else:
                upload_root = os.path.dirname(paths[0])
        else:
            upload_root = ''
        
        for file_data in files_data:
            file_path = file_data['path']
            content = file_data['content']
            
            logger.info(f"Processing {file_path} from memory")
            
            try:
                # 1. Create FILE node (without disk file)
                file_hash = self.ingestor.calculate_file_hash_from_content(content)
                relative_path = os.path.relpath(file_path, upload_root) if upload_root else file_path
                file_name = os.path.basename(file_path)
                
                # Determine language
                ext = os.path.splitext(file_name)[1]
                language = Config.ALLOWED_EXTENSIONS.get(ext, "UNKNOWN")
                
                # 1. Determine Status (Project check & Hash compare)
                status = "TO-BE" # Default to TO-BE (New/Changed)
                
                if project:
                    # Check existing file node
                    existing_node = self.connector.execute_query(
                        "MATCH (f:FILE {path: $path, project: $project}) RETURN f.hash as hash",
                        {"path": relative_path, "project": project}
                    )
                    
                    if existing_node:
                        # File exists, check hash
                        old_hash = existing_node[0]['hash']
                        if old_hash == file_hash:
                            status = "AS-IS"
                        else:
                            status = "TO-BE"
                    else:
                        # File does not exist -> TO-BE
                        status = "TO-BE"

                query = """
                MERGE (f:FILE {path: $path, project: $project})
                SET f.name = $name,
                    f.hash = $hash,
                    f.language = $language,
                    f.status = $status
                """
                
                self.connector.execute_query(query, {
                    "path": relative_path,
                    "name": file_name,
                    "hash": file_hash,
                    "language": language,
                    "project": project,
                    "status": status
                })
                
                # 2. Architecture Analysis from memory
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
