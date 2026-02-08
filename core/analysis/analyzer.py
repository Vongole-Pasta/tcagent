import logging
import os
import hashlib
from infra.db_client import DBClient
from .flow import Builder as FlowBuilder
from config import Config
from graph_db.queries import CypherQueries

logger = logging.getLogger(__name__)


class Analyzer:
    """
    [분석 조정자 (Orchestrator)]
    전체 파일 분석 프로세스를 관리하고 조정하는 핵심 클래스입니다.
    파일의 변경 사항(생성, 수정, 삭제)을 감지하고, 적절한 빌더(Builder)를 호출하여 그래프 DB를 업데이트합니다.
    """
    def __init__(self, connector: DBClient):
        self.connector = connector
        self.flow_builder = FlowBuilder(connector)

    def process_files_from_memory(self, files_data: list[dict], project: str = None):
        """
        [메모리 파일 처리 파이프라인]
        사용자가 업로드한 파일 목록(files_data)을 받아 분석을 수행합니다.
        디스크 I/O 없이 메모리 상에서 직접 처리하여 속도를 최적화했습니다.
        
        Process Lifecycle:
        1. Cleanup: 이전에 'DELETED'로 마킹된 유령 노드들을 DB에서 영구 삭제합니다.
        2. Snapshot: 현재 DB에 저장된 파일 목록과 해시값을 조회하여 기준점을 잡습니다.
        3. Processing: 업로드된 파일의 해시를 비교하여 상태(NEW, MODIFIED, AS-IS)를 결정하고 분석합니다.
        4. Deletion: 업로드 목록에 없는 기존 파일은 'DELETED'로 마킹하고 그래프에서 격리합니다.
        5. Global Resolution: 변경 사항이 있다면 전체 호출 관계(Call Graph)를 재계산하여 연결성을 복구합니다.
        
        Args:
            files_data (list[dict]): {'path': str, 'content': bytes} 형태의 파일 목록
            project (str): 프로젝트 식별자 (기본값: "default")
            
        Returns:
            list: 업데이트된 파일들의 경로 목록 (Frontend 갱신용)
        """
        updated_files = []
        project = project or "default"
        
        # 1. Cleanup: Remove previously DELETED nodes
        logger.info(f"Cleaning up ghost nodes for project: {project}")
        self.connector.execute_query(CypherQueries.DELETE_PROJECT_DELETED_NODES, {"project": project})
        
        # 2. Snapshot: Get existing files
        existing_nodes = self.connector.execute_query(CypherQueries.GET_PROJECT_FILES_HASH, {"project": project})
        existing_files_map = {row['path']: row['hash'] for row in existing_nodes}
        processed_paths = set()

        # Calculate common root
        if files_data:
            paths = [f['path'] for f in files_data]
            if len(paths) > 1:
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
        
        # 3. Processing
        for file_data in files_data:
            file_path = file_data['path']
            content = file_data['content']
            
            try:
                # file_hash = self.ingestor.calculate_file_hash_from_content(content)
                file_hash = hashlib.sha256(content).hexdigest()
                relative_path = os.path.relpath(file_path, upload_root) if upload_root else file_path
                file_name = os.path.basename(file_path)
                processed_paths.add(relative_path)
                
                # Determine Language
                ext = os.path.splitext(file_name)[1]
                language = Config.ALLOWED_EXTENSIONS.get(ext, "UNKNOWN")
                
                # Determine Status
                if relative_path not in existing_files_map:
                    status = "NEW"
                elif existing_files_map[relative_path] != file_hash:
                    status = "MODIFIED"
                else:
                    status = "AS-IS"

                logger.info(f"Processing {relative_path}: {status}")

                # Update Node
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

                if status in ["NEW", "MODIFIED", "AS-IS"]: # AS-IS도 분석은 다시 돌려서 관계 복구/확인 (또는 생략 가능하지만 안전하게 수행)
                    # 사실 AS-IS면 파싱 건너뛰어도 되지만, 그래프 연결성이 끊어질 수 있으니(다른 파일이 바껴서) 
                    # 'Flow'는 다시 봐야 할 수도 있음. 하지만 'Architecture'는 내부 구조라 그대로일 것.
                    # 여기서는 사용자 요청에 따라 '상태' 관리를 우선하므로, 
                    # 일단 다 돌리되, 최적화는 나중에.
                    self.flow_builder.process_file_from_content(relative_path, content)
                    updated_files.append(relative_path)
                
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")

        # 4. Deletion Detection
        all_existing_paths = set(existing_files_map.keys())
        deleted_paths = all_existing_paths - processed_paths
        
        for deleted_path in deleted_paths:
            logger.info(f"Marking {deleted_path} as DELETED")
            self.connector.execute_query(CypherQueries.MARK_FILE_DELETED_AND_ISOLATE, {
                "path": deleted_path,
                "project": project
            })
            updated_files.append(deleted_path) # Include in updated list so frontend refreshes

        # 5. Global Resolution (only if needed)
        # Always resolve if any file was touched or deleted to ensure graph consistency
        if updated_files:
            logger.info("Re-resolving global call topology...")
            self.flow_builder._resolve_calls()
            
        return updated_files
