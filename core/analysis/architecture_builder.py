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

    def process_file(self, file_path: str):
        """
        기존 방식: 디스크에 저장된 파일을 읽어서 처리
        (하위 호환성을 위해 유지)
        """
        self._cleanup_file_data(file_path)
        # file_path는 DB의 상대 경로 -> 절대 경로로 변환 필요
        absolute_path = os.path.join(Config.TARGET_DIR, file_path)
        _, ext = os.path.splitext(file_path)
        try:
            # 1. 파싱
            parser = ParserFactory.get_parser(ext)
            language = ParserFactory.get_language(ext)
            
            with open(absolute_path, "rb") as f:
                source_code = f.read()
            
            tree = parser.parse(source_code)
            
            logger.debug(f"Parsing {file_path} with {ext}")

            # 2. 쿼리 실행
            if ext == ".py":
                self._analyze_python(language, tree.root_node, source_code, file_path)
            elif ext == ".java":
                self._analyze_java(language, tree.root_node, source_code, file_path)
            elif ext in [".ts", ".tsx", ".js", ".jsx"]:
                 self._analyze_typescript(language, tree.root_node, source_code, file_path)

        except Exception as e:
            logger.error(f"Failed to process {file_path}: {e}")

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
            if ext == ".py":
                self._analyze_python(language, tree.root_node, content, file_path)
            elif ext == ".java":
                self._analyze_java(language, tree.root_node, content, file_path)
            elif ext in [".ts", ".tsx", ".js", ".jsx"]:
                 self._analyze_typescript(language, tree.root_node, content, file_path)

        except Exception as e:
            logger.error(f"Failed to process {file_path} from memory: {e}")

    def _analyze_python(self, language, node, source, file_path):
        # Python Class Query
        query_str = """
        (class_definition
            name: (identifier) @class.name
        )
        """
        try:
            query = language.query(query_str)
            captures = query.captures(node)
            
            # infer package from directory
            dir_name = os.path.dirname(file_path).replace("/", ".")
            
            for n, name in captures:
                if name == "class.name":
                    class_name = source[n.start_byte:n.end_byte].decode("utf8")
                    full_name = class_name
                    logger.info(f"[PY] Found class: {class_name}")
                    # class_source = source[n.start_byte:n.end_byte].decode("utf8") # Removed source
                    self._create_type_decl(class_name, full_name, file_path, package_name=dir_name, type_str="CLASS")
        except Exception as e:
            logger.warning(f"Python query error: {e}")

        except Exception as e:
            logger.warning(f"Python global query error: {e}")


        # Create Namespace from directory
        dir_name = os.path.dirname(file_path).replace("/", ".")
        if dir_name:
             self._create_namespace(dir_name, file_path)

    def _analyze_java(self, language, node, source, file_path):
        query_str = """
        (package_declaration
            (scoped_identifier) @package.name
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

    def _analyze_typescript(self, language, node, source, file_path):
        # JS/TS Class identifier can be identifier or type_identifier
        # Also handles interface for TS
        query_str = """
        (class_declaration
            name: (_) @class.name
        )
        (interface_declaration
            name: (_) @interface.name
        )
        """
        try:
            query = language.query(query_str)
            captures = query.captures(node)
            
            # infer package from directory
            dir_name = os.path.dirname(file_path).replace("/", ".")

            for n, name in captures:
                if name == "class.name" or name == "interface.name":
                    class_name = source[n.start_byte:n.end_byte].decode("utf8")
                    logger.info(f"[TS/JS] Found type: {class_name}")
                    # class_source = source[n.start_byte:n.end_byte].decode("utf8") # Removed source
                    
                    type_str = "INTERFACE" if name == "interface.name" else "CLASS"
                    self._create_type_decl(class_name, class_name, file_path, package_name=dir_name, type_str=type_str)
        except Exception as e:
            logger.warning(f"TS/JS query error in {file_path}: {e}")

        except Exception as e:
             logger.warning(f"TS/JS global query error: {e}")


        # Create Namespace from directory
        dir_name = os.path.dirname(file_path).replace("/", ".")
        if dir_name:
             self._create_namespace(dir_name, file_path)

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
        MERGE (f)-[:AST]->(t)
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
        MERGE (f)-[:AST]->(n)
        """
        try:
            self.connector.execute_query(query, {
                "file_path": file_path,
                "name": name
            })
        except Exception as e:
             logger.error(f"DB Error: {e}")

    def _create_member(self, name, type_info, file_path, line_number, owner_type_full_name=None):
        # Generate unique ID for the member
        if owner_type_full_name:
            member_id = f"{owner_type_full_name}.{name}"
        else:
            member_id = f"{file_path}:global:{name}"

        # embedding = self.embedding_service.get_embedding(f"{name}: {type_info}")
        embedding = None
        
        query = """
        MERGE (m:MEMBER {id: $id})
        SET m.name = $name,
            m.type = $type,
            m.lineNumber = $line_number,
            m.embedding = $embedding
        """
        
        # Link to owner
        if owner_type_full_name:
            query += """
            WITH m
            MATCH (t:TYPE_DECL {fullName: $owner_full_name})
            MERGE (t)-[:AST]->(m)
            """
        else:
            query += """
            WITH m
            MATCH (f:FILE {path: $file_path})
            MERGE (f)-[:AST]->(m)
            """

        try:
            self.connector.execute_query(query, {
                "id": member_id,
                "name": name,
                "type": type_info,
                "line_number": line_number,
                "embedding": embedding,
                "owner_full_name": owner_type_full_name,
                "file_path": file_path
            })
        except Exception as e:
             logger.error(f"DB Error (MEMBER): {e}")

    def _cleanup_file_data(self, file_path):
        """재처리를 위해 기존 아키텍처 노드(Class, Member 등)를 삭제합니다."""
        query = """
        MATCH (f:FILE {path: $file_path})
        OPTIONAL MATCH (f)-[:AST]->(n)
        WHERE n:TYPE_DECL OR n:NAMESPACE_BLOCK OR n:MEMBER
        DETACH DELETE n
        """
        try:
            self.connector.execute_query(query, {"file_path": file_path})
            logger.info(f"Cleaned up architecture data for {file_path}")
        except Exception as e:
            logger.error(f"Failed to cleanup architecture data for {file_path}: {e}")
