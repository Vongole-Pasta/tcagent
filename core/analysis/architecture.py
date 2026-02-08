from .parser import Factory
from infra.db_client import DBClient

import os
import logging

logger = logging.getLogger(__name__)

class Builder:
    """
    [아키텍처 빌더]
    소스 코드를 파싱하여 프로젝트의 뼈대(Structure)를 그래프 DB에 구축하는 역할을 합니다.
    주로 파일(FILE)과 클래스/인터페이스(TYPE) 노드를 생성하고 연결합니다.
    """
    def __init__(self, connector: DBClient):
        self.connector = connector
        # self.embedding_service = EmbeddingService()

    def process_file_from_content(self, file_path: str, content: bytes):
        """
        [메모리 기반 파일 구조 분석]
        업로드된 파일의 내용을 파싱하여 클래스(TYPE) 구조를 추출합니다.
        기존 데이터를 정리(Cleanup)한 후 새로 분석(Analyze)합니다.
        
        Args:
            file_path: 파일의 상대 경로 (DB 저장 및 식별용)
            content: 파일의 바이너리 내용
        """
        self._cleanup_file_data(file_path)
        _, ext = os.path.splitext(file_path)
        try:
            # 1. 적절한 파서 및 언어 설정 가져오기
            parser = Factory.get_parser(ext)
            language = Factory.get_language(ext)
            
            # 2. 소스 코드 파싱 (Tree-sitter)
            tree = parser.parse(content)
            
            logger.debug(f"Parsing {file_path} from memory with {ext}")

            # 3. 언어별 구조 분석 실행
            if ext == ".java":
                self._analyze_java(language, tree.root_node, content, file_path)

        except Exception as e:
            logger.error(f"Failed to process {file_path} from memory: {e}")

    def _analyze_java(self, language, node, source, file_path):
        """
        [Java 구조 분석]
        Java 파일에서 패키지명과 클래스(Class) 정의를 추출합니다.
        추출된 정보는 DB에 TYPE 노드로 저장됩니다.
        """
        # 패키지명과 클래스명을 추출하기 위한 Tree-sitter 쿼리
        query_str = """
        (package_declaration
            [
                (scoped_identifier)
                (identifier)
            ] @package.name
        )
        (class_declaration
            name: (identifier) @class.name
        )
        """
        try:
            query = language.query(query_str)
            captures = query.captures(node)
            
            package_name = ""
            # 1. 패키지명 추출
            for n, name in captures:
                if name == "package.name":
                    package_name = source[n.start_byte:n.end_byte].decode("utf8")

            # 2. 클래스명 추출 및 노드 생성
            for n, name in captures:
                if name == "class.name":
                    # Inner Class는 FlowBuilder에서 처리하므로 여기서는 건너뜁니다.
                    # (ArchitectureBuilder는 파일의 최상위 뼈대만 담당)
                    parent_type = n.parent.parent.type if n.parent else ""
                    if parent_type == "class_body":
                         logger.debug(f"Skipping inner class in ArchitectureBuilder: {name}")
                         continue

                    class_name = source[n.start_byte:n.end_byte].decode("utf8")
                    
                    # 고유 식별자 생성 (Package + FileName + ClassName)
                    file_name_no_ext = os.path.splitext(os.path.basename(file_path))[0]
                    full_name = f"{package_name}.{file_name_no_ext}.{class_name}" if package_name else f"{file_name_no_ext}.{class_name}"
                    
                    logger.info(f"[JAVA] Found class: {class_name}")
                    # DB에 TYPE 노드 생성 요청
                    self._create_type_decl(class_name, full_name, file_path, package_name=package_name, type_str="CLASS")
        except Exception as e:
            logger.warning(f"Java query error: {e}")

    def extract_and_load(self):
        """
        [전체 재분석] (Disk I/O)
        DB에 등록된 모든 파일을 스캔하여 구조를 다시 분석합니다.
        """
        query = "MATCH (f:FILE) RETURN f.path AS path"
        results = self.connector.execute_query(query)
        logger.info(f"Found {len(results)} files to analyze.")
        
        for record in results:
            self.process_file(record["path"])

    def _create_type_decl(self, name, full_name, file_path, package_name="", type_str="CLASS"):
        """
        [TYPE 노드 생성]
        분석된 클래스 정보를 바탕으로 그래프 DB에 노드를 생성하고 파일과 연결합니다.
        
        Query Structure:
        (FILE) -[:CONTAINS]-> (TYPE)
        """
        embedding = None
        
        query = """
        MATCH (f:FILE {path: $file_path})
        MERGE (t:TYPE {fullName: $full_name})
        SET t.name = $name,
            t.type = $type,
            t.embedding = $embedding
        
        // 파일 노드에 패키지 정보 업데이트 (검색 편의성)
        SET f.package = $package

        MERGE (f)-[:CONTAINS]->(t)
        """
        try:
            self.connector.execute_query(query, {
                "file_path": file_path,
                "full_name": full_name,
                "name": name,
                "package": package_name,
                "type": type_str,
                "embedding": embedding
            })
        except Exception as e:
             logger.error(f"DB Error: {e}")

    def _cleanup_file_data(self, file_path):
        """
        [데이터 정리]
        파일 재분석 전, 해당 파일에 속한 기존의 구조 정보(TYPE 노드 등)를 삭제합니다.
        중복 생성을 방지하고 최신 상태를 유지하기 위함입니다.
        """
        query = """
        MATCH (f:FILE {path: $file_path})
        OPTIONAL MATCH (f)-[:CONTAINS]->(n)
        WHERE n:TYPE
        DETACH DELETE n
        """
        try:
            self.connector.execute_query(query, {"file_path": file_path})
            logger.info(f"Cleaned up architecture data for {file_path}")
        except Exception as e:
            logger.error(f"Failed to cleanup architecture data for {file_path}: {e}")

