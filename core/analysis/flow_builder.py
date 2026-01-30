from infra.db_client import DBClient
import uuid
from config import Config
import os
import logging
from core.analysis.strategies.java import JavaFlowStrategy
from core.analysis.parser_factory import ParserFactory

logger = logging.getLogger(__name__)

class FlowBuilder:
    def __init__(self, connector: DBClient):
        self.connector = connector
        # Java Strategy Only
        self.strategies = {
            ".java": JavaFlowStrategy(connector),
        }

    def process_file_from_content(self, file_path: str, content: bytes):
        """신규 방식: 메모리에 있는 파일 내용을 직접 처리"""
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
            else:
                 # Should not reach here in Java-only mode, but for safety
                pass

        except Exception as e:
            logger.error(f"Failed to process flow for {file_path} from memory: {e}")

    def _prune_nodes(self, file_path, scan_id):
        """
        Smart Update 후처리:
        이번 스캔(scan_id)에서 갱신되지 않은(즉, 소스에서 삭제된) 노드를 제거합니다.
        """
        query = """
        MATCH (f:FILE {path: $file_path})
        
        // 1. 해당 파일에 속한 메서드 중 last_scan_id가 현재 id와 다른 것 찾기
        MATCH (f)-[:AST|DEFINES|CONTAINS*1..3]->(m:METHOD)
        WHERE m.last_scan_id <> $scan_id
        
        // 2. 메서드의 자식 노드들도 같이 삭제 (파라미터, 호출 등)
        OPTIONAL MATCH (m)-[:Contains|HAS_PARAM|HAS_EXIT|ANNOTATED_BY]->(child)
        WHERE child:CONTROL_STRUCTURE OR child:CALL OR child:PARAMETER OR child:RETURN OR child:ANNOTATION
        
        // 3. 자식의 자식 (Literal 등)
        OPTIONAL MATCH (child)-[:CONTAINS]->(lit:LITERAL)
        
        DETACH DELETE m, child, lit
        """
        try:
            self.connector.execute_query(query, {"file_path": file_path, "scan_id": scan_id})
            logger.info(f"Pruned stale nodes for {file_path} (ScanID: {scan_id})")
        except Exception as e:
            logger.error(f"Pruning Error ({file_path}): {e}")

    def _resolve_calls(self):
        """
        토폴로지 최적화:
        임시 CALL 노드를 직접적인 CALLS 엣지 또는 ExternalCall 노드로 변환합니다.
        """
        logger.info("Resolving function calls (Topology Optimization)...")
        
        # 1. 내부 해석 (엄격 모드)
        # CASE 1: 명시적 객체 호출 (예: Service.method())
        query_internal_obj = """
        MATCH (source:METHOD)-[:HAS_CALL]->(c:CALL)
        WHERE c.objectName IS NOT NULL AND c.objectName <> ''
        
        MATCH (target:METHOD {name: c.methodName})
        MATCH (target)<-[:CONTAINS]-(targetClass:CLASS)
        
        // objectName이 Class 이름과 일치하는지 확인 (예: MemberService vs memberService)
        WHERE toLower(targetClass.name) = toLower(c.objectName)
           OR targetClass.name = c.objectName
        
        MERGE (source)-[r:CALLS]->(target)
        SET r.count = c.count
        WITH c
        DETACH DELETE c
        """
        
        # CASE 2: 암시적/This 호출
        query_internal_this = """
        MATCH (source:METHOD)-[:HAS_CALL]->(c:CALL)
        WHERE c.objectName IS NULL OR c.objectName = ''
        
        MATCH (source)<-[:CONTAINS]-(sourceClass:CLASS)
        MATCH (target:METHOD {name: c.methodName})
        MATCH (target)<-[:CONTAINS]-(targetClass:CLASS)
        
        WHERE sourceClass = targetClass
        
        MERGE (source)-[r:CALLS]->(target)
        SET r.count = c.count
        WITH c
        DETACH DELETE c
        """
        
        try:
            self.connector.execute_query(query_internal_obj)
            self.connector.execute_query(query_internal_this)
            logger.info("Internal calls resolved (Strict Mode).")
        except Exception as e:
            logger.error(f"Internal Resolution Error: {e}")

        # 2. 외부 호출 해석
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
