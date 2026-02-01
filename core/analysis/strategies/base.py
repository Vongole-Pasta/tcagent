from abc import ABC, abstractmethod
import logging
import json
import hashlib
from infra.embedding import EmbeddingService

logger = logging.getLogger(__name__)

class BaseFlowStrategy(ABC):
    def __init__(self, connector):
        self.connector = connector
        self.embedding_service = EmbeddingService()

    @abstractmethod
    def process(self, tree, source_code, file_path):
        pass

    def _create_method(self, name, signature, file_path, line_number, source_code="", owner_full_name=None):
        body_hash = hashlib.sha256(source_code.encode('utf-8')).hexdigest()
        
        # Cost Optimization: Check existing embedding
        embedding = None
        existing_info = self._get_existing_method_embedding(file_path, signature)
        
        if existing_info and existing_info.get("bodyHash") == body_hash and existing_info.get("embedding"):
            # 기존과 소스가 같고 임베딩이 있으면 재사용
            embedding = existing_info["embedding"]
        else:
            # 변경되었거나 없으면 API 호출
            embedding = self.embedding_service.get_embedding(source_code)
        
        query = """
        MATCH (f:FILE {path: $file_path})
        MERGE (m:METHOD {signature: $signature})
        ON CREATE SET 
            m.name = $name, 
            m.lineNumber = $line_number,
            m.source = $source,
            m.bodyHash = $body_hash,
            m.embedding = $embedding,
            m.testStatus = 'DIRTY',
            m.lastBodyHash = ''
        ON MATCH SET
            m.testStatus = CASE WHEN m.bodyHash <> $body_hash THEN 'DIRTY' ELSE m.testStatus END,
            m.name = $name,
            m.lineNumber = $line_number,
            m.source = $source,
            m.bodyHash = $body_hash,
            m.embedding = $embedding
        """
        
        if owner_full_name:
            # Link to TYPE_DECL (Class)
            query += """
            WITH m, f
            MATCH (t:TYPE_DECL {fullName: $owner_full_name})
            MERGE (t)-[:AST]->(m)
            """
        else:
            # Fallback: Link to FILE
            query += """
            MERGE (f)-[:AST]->(m)
            """

        try:
            self.connector.execute_query(query, {
                "file_path": file_path, "signature": signature, 
                "name": name, "line_number": line_number,
                "source": source_code, "body_hash": body_hash,
                "embedding": embedding,
                "owner_full_name": owner_full_name
            })
        except Exception as e:
             logger.error(f"DB Error (Method): {e}")

    def _get_existing_method_embedding(self, file_path, signature):
        query = """
        MATCH (f:FILE {path: $file_path})-[:Contains]->(m:METHOD {signature: $signature})
        RETURN m.bodyHash as bodyHash, m.embedding as embedding
        LIMIT 1
        """
        try:
            results = self.connector.execute_query(query, {"file_path": file_path, "signature": signature})
            if results:
                return results[0]
        except Exception as e:
            logger.error(f"DB Error (GetMethod): {e}")
        return None

    def _create_control_structure(self, type_name, file_path, line_number, condition=None, parent_method_name=None):
        query = ""
        # Link to METHOD if parent_method_name is provided
        if parent_method_name:
            query = """
            MATCH (f:FILE {path: $file_path})-[:AST*]->(m:METHOD)
            WHERE m.signature = $method_signature OR m.name = $method_name
            CREATE (c:CONTROL_STRUCTURE {type: $type, lineNumber: $line_number})
            MERGE (m)-[:Contains]->(c)
            """
            # If condition exists, set it
            if condition:
                query += "SET c.condition = $condition "
        else:
            # Fallback to FILE linking if no parent method found (e.g. top level)
            query = """
            MATCH (f:FILE {path: $file_path})
            CREATE (c:CONTROL_STRUCTURE {type: $type, lineNumber: $line_number})
            MERGE (f)-[:Contains]->(c)
            """
            if condition:
                query += "SET c.condition = $condition "

        try:
            params = {
                "file_path": file_path, 
                "type": type_name, 
                "line_number": line_number,
                "method_name": parent_method_name,
                "method_signature": parent_method_name, # Current impl uses name as signature
                "condition": condition
            }
            self.connector.execute_query(query, params)
        except Exception as e:
             logger.error(f"DB Error (Control): {e}")

    def _create_call(self, method_name, file_path, line_number, parent_method_name=None):
        if parent_method_name:
            query = """
            MATCH (f:FILE {path: $file_path})-[:AST*]->(m:METHOD)
            WHERE m.signature = $method_signature OR m.name = $method_name_param
            CREATE (c:CALL {methodName: $method_name, lineNumber: $line_number})
            MERGE (m)-[:Contains]->(c)
            """
        else:
            query = """
            MATCH (f:FILE {path: $file_path})
            CREATE (c:CALL {methodName: $method_name, lineNumber: $line_number})
            MERGE (f)-[:Contains]->(c)
            """
        try:
            params = {
                "file_path": file_path, 
                "method_name": method_name, 
                "line_number": line_number,
                "method_signature": parent_method_name,
                "method_name_param": parent_method_name
            }
            if parent_method_name:
                 self.connector.execute_query(query, params)
            else:
                 self.connector.execute_query(query, {
                    "file_path": file_path, "method_name": method_name, "line_number": line_number
                })

        except Exception as e:
             logger.error(f"DB Error (Call): {e}")

    def _create_parameter(self, name, type_name, index, is_optional, parent_method_signature, file_path):
        query = """
        MATCH (f:FILE {path: $file_path})-[:AST*]->(m:METHOD {signature: $method_signature})
        CREATE (p:PARAMETER {name: $name, type: $type, index: $index, isOptional: $is_optional})
        MERGE (m)-[:HAS_PARAM]->(p)
        """
        try:
            self.connector.execute_query(query, {
                "file_path": file_path, "method_signature": parent_method_signature,
                "name": name, "type": type_name, "index": index, "is_optional": is_optional
            })
        except Exception as e:
            logger.error(f"DB Error (Parameter): {e}")

    def _create_annotation(self, name, parameters, file_path, parent_type, parent_method_signature, parent_param_name=None):
        props = {"name": name}
        if parameters:
            props["parameters"] = json.dumps(parameters) if isinstance(parameters, (dict, list)) else str(parameters)
        
        query = ""
        if parent_type == "METHOD":
            query = """
            MATCH (f:FILE {path: $file_path})-[:AST*]->(m:METHOD {signature: $method_sig})
            CREATE (a:ANNOTATION {name: $name, parameters: $params})
            MERGE (m)-[:ANNOTATED_BY]->(a)
            """
        elif parent_type == "PARAMETER":
            query = """
            MATCH (f:FILE {path: $file_path})-[:AST*]->(m:METHOD {signature: $method_sig})
            MATCH (m)-[:HAS_PARAM]->(p:PARAMETER {name: $param_name})
            CREATE (a:ANNOTATION {name: $name, parameters: $params})
            MERGE (p)-[:ANNOTATED_BY]->(a)
            """
        
        try:
            params = {
                "file_path": file_path, "method_sig": parent_method_signature,
                "name": name, "params": props.get("parameters", ""),
                "param_name": parent_param_name
            }
            self.connector.execute_query(query, params)
        except Exception as e:
            logger.error(f"DB Error (Annotation): {e}")

    def _create_return(self, type_name, expression, parent_method_signature, file_path):
        query = """
        MATCH (f:FILE {path: $file_path})-[:AST*]->(m:METHOD {signature: $method_signature})
        CREATE (r:RETURN {type: $type, expression: $expression})
        MERGE (m)-[:HAS_EXIT]->(r)
        """
        try:
            self.connector.execute_query(query, {
                "file_path": file_path, "method_signature": parent_method_signature,
                "type": type_name, "expression": expression
            })
        except Exception as e:
            logger.error(f"DB Error (Return): {e}")

    def _create_literal(self, value, type_name, parent_control_line, parent_method_signature, file_path):
        query = """
        MATCH (f:FILE {path: $file_path})-[:AST*]->(m:METHOD {signature: $method_signature})
        MATCH (m)-[:Contains]->(c:CONTROL_STRUCTURE {lineNumber: $line_number})
        CREATE (l:LITERAL {value: $value, type: $type})
        MERGE (c)-[:CONTAINS]->(l)
        """
        try:
            self.connector.execute_query(query, {
                "file_path": file_path, "method_signature": parent_method_signature,
                "line_number": parent_control_line,
                "value": str(value), "type": type_name
            })
        except Exception as e:
            logger.error(f"DB Error (Literal): {e}")
