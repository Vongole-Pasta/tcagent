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
            else:
                # Others: Classic Reset (Delete + Create)
                self._cleanup_file_flow_data(file_path)
                strategy.process(tree, content, file_path)

        except Exception as e:
            logger.error(f"Failed to process flow for {file_path} from memory: {e}")

    def _cleanup_file_flow_data(self, file_path):
        """파일 재분석 전 기존 Flow 데이터 삭제 (중복 방지)"""
        query = """
        MATCH (f:FILE {path: $file_path})
        
        // 1. 메서드 자식 노드 (제어구조, 호출, 파라미터, 반환, 어노테이션)
        // 메서드는 FILE 또는 TYPE_DECL로부터 [:CONTAINS]로 연결될 수 있음
        OPTIONAL MATCH (f)-[:CONTAINS*1..2]->(m:METHOD)
        OPTIONAL MATCH (m)-[:Contains|HAS_PARAM|HAS_EXIT|ANNOTATED_BY|HAS_CALL]->(child)
        WHERE child:CONTROL_STRUCTURE OR child:CALL OR child:PARAMETER OR child:RETURN OR child:ANNOTATION
        
        // 1.1 제어 구조에 첨부된 리터럴(Literal)
        OPTIONAL MATCH (child)-[:CONTAINS]->(lit:LITERAL)
        DETACH DELETE m, child, lit
        
        // 2. 파일 자식 노드 (최상위 제어구조, 호출) - Contains 또는 AST로 연결? 
        // FlowBuilder는 파일 레벨의 제어/호출에 대해 Contains를 사용함.
        WITH f
        OPTIONAL MATCH (f)-[:Contains]->(child_direct)
        WHERE child_direct:CONTROL_STRUCTURE OR child_direct:CALL
        OPTIONAL MATCH (child_direct)-[:CONTAINS]->(lit_direct:LITERAL)
        DETACH DELETE child_direct, lit_direct
        """
        try:
            self.connector.execute_query(query, {"file_path": file_path})
        except Exception as e:
            logger.error(f"Cleanup Error ({file_path}): {e}")

    def _prune_nodes(self, file_path, scan_id):
        """
        Smart Update 후처리:
        이번 스캔(scan_id)에서 갱신되지 않은(즉, 소스에서 삭제된) 노드를 제거합니다.
        """
        query = """
        MATCH (f:FILE {path: $file_path})
        
        // 1. 해당 파일에 속한 메서드 중 last_scan_id가 현재 id와 다른 것 찾기
        // 1. 해당 파일에 속한 메서드 중 last_scan_id가 현재 id와 다른 것 찾기
        MATCH (f)-[:CONTAINS*1..3]->(m:METHOD)
        WHERE m.last_scan_id <> $scan_id
        
        // 2. 메서드의 자식 노드들도 같이 삭제 (파라미터, 호출 등)
        OPTIONAL MATCH (m)-[:Contains|HAS_PARAM|HAS_EXIT|ANNOTATED_BY|HAS_CALL]->(child)
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
        MATCH (target)<-[:CONTAINS]-(targetClass:TYPE_DECL)
        
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
        
        MATCH (source)<-[:CONTAINS]-(sourceClass:TYPE_DECL)
        MATCH (target:METHOD {name: c.methodName})
        MATCH (target)<-[:CONTAINS]-(targetClass:TYPE_DECL)
        
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
