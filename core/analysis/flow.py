from graph_db.client import DBClient
import hashlib
import uuid

import os
import logging
from core.analysis.lang.java.java_parser import JavaFlowStrategy
from .parser import Factory

logger = logging.getLogger(__name__)


class Builder:
    """
    [플로우 빌더]
    메서드 레벨의 상세 분석(Flow Analysis)을 담당합니다.
    각 파일의 메서드를 추출(Method Node)하고, 메서드 간의 호출 관계(Call Relationship)를 연결합니다.
    언어별 전략(Strategy) 패턴을 사용하여 확장성을 가집니다.
    """
    def __init__(self, connector: DBClient):
        self.connector = connector
        self.strategies = {
            ".java": JavaFlowStrategy(connector),
        }

    def process_file_from_content(self, file_path: str, content: bytes):
        """
        [메모리 기반 플로우 분석]
        파일 내용을 파싱하여 메서드 정의와 호출 관계를 추출합니다.
        
        Args:
            file_path (str): 파일 경로
            content (bytes): 파일 내용
        """

        _, ext = os.path.splitext(file_path)
        
        strategy = self.strategies.get(ext)
        if not strategy:
            return

        try:
            parser = Factory.get_parser(ext)
            tree = parser.parse(content)
            
            if ext == ".java":
                # [Java 스마트 업데이트]
                # 전체 삭제 후 재생성이 아니라, 변경된 부분만 갱신(Upsert)하고
                # 없어진 메서드만 가지치기(Prune)하는 방식입니다.
                scan_id = str(uuid.uuid4())
                strategy.process(tree, content, file_path, scan_id)
                self._prune_nodes(file_path, scan_id)


        except Exception as e:
            logger.error(f"Failed to process flow for {file_path} from memory: {e}")

    def _prune_nodes(self, file_path, scan_id):
        """
        [메서드 가지치기 (Pruning)]
        Smart Update의 후처리 단계입니다.
        이번 스캔(scan_id)에서 발견되지 않은 메서드는 소스 코드에서 삭제된 것으로 간주합니다.
        해당 메서드를 'DELETED'로 마킹하고, 다른 메서드와의 호출 관계(Flow)를 끊어냅니다.
        """
        query = """
        MATCH (f:FILE {path: $file_path})
        MATCH (f)-[:CONTAINS*1..3]->(m:METHOD)
        
        WHERE m.last_scan_id <> $scan_id
        
        // Mark as DELETED
        SET m.status = 'DELETED'
        
        WITH m
        // [격리] 다른 메서드와의 호출 관계 제거 (분석 방해 방지)
        OPTIONAL MATCH (m)-[r:CALLS]-()
        DELETE r
        
        WITH m
        // [정리] 내부 AST 호출 노드 제거
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
        [호출 관계 해결 (Topology Resolution)]
        1차 분석에서 생성된 임시 `CALL` 노드를 실제 `METHOD` 노드 간의 `CALLS` 관계(Edge)로 변환합니다.
        전체 그래프의 연결성을 완성하는 중요한 단계입니다.
        
        Logic:
        1. 내부 호출 (Internal): 
           - 호출한 객체명(objectName)과 대상 클래스명을 매칭 (엄격 모드)
           - this 호출(objName 없음)은 같은 클래스 내 메서드와 매칭
        2. 외부 호출 (External):
           - 내부에서 찾지 못한 호출은 외부 라이브러리나 API 호출로 간주하여 `ExternalCall` 노드로 분류
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
