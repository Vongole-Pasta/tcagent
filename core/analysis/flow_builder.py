from infra.db_client import DBClient
import hashlib
import uuid

import os
import logging
from core.analysis.strategies.java import JavaFlowStrategy
from core.analysis.parser_factory import ParserFactory

logger = logging.getLogger(__name__)

class FlowBuilder:
    def __init__(self, connector: DBClient):
        self.connector = connector
        self.strategies = {
            ".java": JavaFlowStrategy(connector),
        }



    def process_file_from_content(self, file_path: str, content: bytes):
        """신규 방식: 메모리에 있는 파일 내용을 직접 처리"""
        # self._cleanup_file_flow_data(file_path) # Moved to inside conditionals
        _, ext = os.path.splitext(file_path)
        
        strategy = self.strategies.get(ext)
        if not strategy:
            return

        try:
            parser = ParserFactory.get_parser(ext)
            tree = parser.parse(content)
            
            if ext == ".java":
                # Java: Smart Update (Upsert + Prune)
                scan_id = str(uuid.uuid4())
                strategy.process(tree, content, file_path, scan_id)
                self._prune_nodes(file_path, scan_id)
            # Removed unreachable else block for non-Java files as strategy list only contains Java

        except Exception as e:
            logger.error(f"Failed to process flow for {file_path} from memory: {e}")

    def _prune_nodes(self, file_path, scan_id):
        """
        Smart Update 후처리:
        갱신되지 않은 메서드를 'DELETED' 상태로 변경하고, 호출 관계(Flow)를 끊습니다.
        (노드 자체와 구조적 자식들은 유지하여 소스 확인 가능하게 함)
        """
        query = """
        MATCH (f:FILE {path: $file_path})
        MATCH (f)-[:CONTAINS*1..3]->(m:METHOD)
        
        WHERE m.last_scan_id <> $scan_id
        
        // Mark as DELETED
        SET m.status = 'DELETED'
        
        WITH m
        // Remove Flow Relationships (Isolation)
        // Outgoing/Incoming calls are removed so it doesn't affect flow analysis
        OPTIONAL MATCH (m)-[r:CALLS]-()
        DELETE r
        
        WITH m
        // Remove internal AST calls (orphaned references)
        OPTIONAL MATCH (m)-[r:HAS_CALL]->()
        DELETE r
        """
        try:
            self.connector.execute_query(query, {"file_path": file_path, "scan_id": scan_id})
            logger.info(f"Marked stale methods as DELETED for {file_path} (ScanID: {scan_id})")
        except Exception as e:
            logger.error(f"Pruning Error ({file_path}): {e}")



    def _resolve_calls(self):
        """
        토폴로지 최적화:
        임시 CALL 노드를 직접적인 CALLS 엣지 또는 ExternalCall 노드로 변환합니다.
        
        로직 개선 (카테시안 곱 방지 및 엄격한 매칭):
        1. 문맥 인식 내부 해석:
           - CALL objectName과 대상 Class이름 매칭 (대소문자 무시)
           - 또는 objectName이 비어있으면(this.method) 같은 클래스 메서드 매칭
        2. 외부 호출 해석:
           - 매칭되지 않은 나머지 CALL은 고유한 ExternalCall 노드로 생성하여 연결
        """
        logger.info("Resolving function calls (Topology Optimization)...")
        
        # 1. 내부 해석 (엄격 모드)
        # CASE 1: 명시적 객체 호출 (예: Service.method() 또는 var.method())
        # objectName을 클래스명과 매칭 시도 (휴리스틱)
        query_internal_obj = """
        MATCH (source:METHOD)-[:HAS_CALL]->(c:CALL)
        WHERE c.objectName IS NOT NULL AND c.objectName <> ''
        
        MATCH (target:METHOD {name: c.methodName})
        MATCH (target)<-[:CONTAINS]-(targetClass:TYPE)
        
        // objectName이 Class 이름과 일치하는지 확인 (예: MemberService vs memberService)
        WHERE toLower(targetClass.name) = toLower(c.objectName)
           OR targetClass.name = c.objectName
        
        MERGE (source)-[r:CALLS]->(target)
        SET r.count = c.count
        WITH c
        DETACH DELETE c
        """
        
        # CASE 2: 암시적/This 호출
        # 상속 등을 고려해 모든 클래스의 메서드를 찾을 수도 있으나,
        # 단순 최적화를 위해 동일 클래스 우선 매칭
        query_internal_this = """
        MATCH (source:METHOD)-[:HAS_CALL]->(c:CALL)
        WHERE c.objectName IS NULL OR c.objectName = ''
        
        MATCH (source)<-[:CONTAINS]-(sourceClass:TYPE)
        MATCH (target:METHOD {name: c.methodName})
        MATCH (target)<-[:CONTAINS]-(targetClass:TYPE)
        
        WHERE sourceClass = targetClass
        
        MERGE (source)-[r:CALLS]->(target)
        SET r.count = c.count
        WITH c
        DETACH DELETE c
        """
        
        try:
            # Run Strict Matching First
            self.connector.execute_query(query_internal_obj)
            self.connector.execute_query(query_internal_this)
            
            # 폴백(Fallback)? 엄격 모드만으로 충분할 수 있음.
            # 만약 's.login()' (s는 MemberService) 같은 케이스를 놓치면, 엄격 모드에서는 ExternalCall이 됨.
            # 오탐(False Positive)을 피하기 위해 허용 가능한 수준.
            
            logger.info("Internal calls resolved (Strict Mode).")
        except Exception as e:
            logger.error(f"Internal Resolution Error: {e}")

        # 2. 외부 호출 해석
        # 남은 CALL 노드들은 외부 호출로 간주함.
        query_external = """
        MATCH (source:METHOD)-[:HAS_CALL]->(c:CALL)
        MERGE (e:ExternalCall {name: c.methodName})
        MERGE (source)-[r:CALLS]->(e)
        SET r.count = c.count
        WITH c
        DETACH DELETE c
        """
        try:
            self.connector.execute_query(query_external)
            logger.info("External calls resolved.")
        except Exception as e:
            logger.error(f"External Resolution Error: {e}")
