from core.analysis.parser_factory import ParserFactory
from infra.db_client import DBClient

from config import Config
import os
import logging

logger = logging.getLogger(__name__)

class ArchitectureBuilder:
    def __init__(self, connector: DBClient):
        self.connector = connector
        # self.embedding_service = EmbeddingService()



    def process_file_from_content(self, file_path: str, content: bytes):
        """
        신규 방식: 메모리에 있는 파일 내용을 직접 처리 (디스크 I/O 없음)
        
        Args:
            file_path: 파일의 상대 경로 (DB 저장용)
            content: 파일의 바이너리 내용
        """
        self._cleanup_file_data(file_path)
        _, ext = os.path.splitext(file_path)
        try:
            # 1. 파싱
            parser = ParserFactory.get_parser(ext)
            language = ParserFactory.get_language(ext)
            
            tree = parser.parse(content)
            
            logger.debug(f"Parsing {file_path} from memory with {ext}")

            # 2. 쿼리 실행
            if ext == ".java":
                self._analyze_java(language, tree.root_node, content, file_path)

        except Exception as e:
            logger.error(f"Failed to process {file_path} from memory: {e}")




        # Create Namespace from directory
        dir_name = os.path.dirname(file_path).replace("/", ".")
        if dir_name:
             self._create_namespace(dir_name, file_path)

    def _analyze_java(self, language, node, source, file_path):
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
            for n, name in captures:
                if name == "package.name":
                    package_name = source[n.start_byte:n.end_byte].decode("utf8")
                    self._create_namespace(package_name, file_path)

            for n, name in captures:
                if name == "class.name":
                    class_name = source[n.start_byte:n.end_byte].decode("utf8")
                    full_name = f"{package_name}.{class_name}" if package_name else class_name
                    logger.info(f"[JAVA] Found class: {class_name}")
                    # class_source = source[n.start_byte:n.end_byte].decode("utf8") # Removed source
                    self._create_type_decl(class_name, full_name, file_path, package_name=package_name, type_str="CLASS")
        except Exception as e:
            logger.warning(f"Java query error: {e}")



    def extract_and_load(self):
        query = "MATCH (f:FILE) RETURN f.path AS path"
        results = self.connector.execute_query(query)
        logger.info(f"Found {len(results)} files to analyze.")
        
        for record in results:
            self.process_file(record["path"])

    def _create_type_decl(self, name, full_name, file_path, package_name="", type_str="CLASS"):
        # embedding = self.embedding_service.get_embedding(source_code) # Source removed
        embedding = None
        
        query = """
        MATCH (f:FILE {path: $file_path})
        MERGE (t:TYPE_DECL {fullName: $full_name})
        SET t.name = $name,
            t.package = $package,
            t.type = $type,
            t.embedding = $embedding
        MERGE (f)-[:CONTAINS]->(t)
        
        // Ensure Package -> File link
        MERGE (p:NAMESPACE_BLOCK {fullName: $package})
        ON CREATE SET p.name = split($package, '.')[-1]
        MERGE (p)-[:CONTAINS]->(f)
        """
        try:
            self.connector.execute_query(query, {
                "file_path": file_path,
                "full_name": full_name,
                "name": name,
                # "line_number": line_number, # Removed
                "package": package_name,
                "type": type_str,
                "embedding": embedding
            })
        except Exception as e:
             logger.error(f"DB Error: {e}")

    def _create_namespace(self, name, file_path):
        query = """
        MATCH (f:FILE {path: $file_path})
        MERGE (n:NAMESPACE_BLOCK {fullName: $name})
        SET n.name = $name
        // Link Package -> File
        MERGE (n)-[:CONTAINS]->(f)
        """
        try:
            self.connector.execute_query(query, {
                "file_path": file_path,
                "name": name
            })
        except Exception as e:
             logger.error(f"DB Error: {e}")



    def _cleanup_file_data(self, file_path):
        """재처리를 위해 기존 아키텍처 노드(Class, Member 등)를 삭제합니다."""
        query = """
        MATCH (f:FILE {path: $file_path})
        OPTIONAL MATCH (f)-[:CONTAINS]->(n)
        WHERE n:TYPE_DECL
        DETACH DELETE n
        """
        try:
            self.connector.execute_query(query, {"file_path": file_path})
            logger.info(f"Cleaned up architecture data for {file_path}")
        except Exception as e:
            logger.error(f"Failed to cleanup architecture data for {file_path}: {e}")
