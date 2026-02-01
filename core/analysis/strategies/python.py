from .base import BaseFlowStrategy
import logging

logger = logging.getLogger(__name__)

class PythonFlowStrategy(BaseFlowStrategy):
    def process(self, tree, source_code, file_path):
        self._extract_methods_python(tree.root_node, source_code, file_path)
        # self._extract_controls_python(tree.root_node, source_code, file_path) # REMOVED: Simplified Granularity
        self._extract_calls_python(tree.root_node, source_code, file_path)

    def _extract_methods_python(self, node, source, file_path):
        from core.analysis.parser_factory import ParserFactory
        language = ParserFactory.get_language(".py")
        query_str = """
        (function_definition
            name: (identifier) @method.name
        )
        """
        try:
            query = language.query(query_str)
            captures = query.captures(node)
            for n, name in captures:
                if name == "method.name":
                    method_name = source[n.start_byte:n.end_byte].decode("utf8")
                    method_node = n.parent
                    method_source = source[method_node.start_byte:method_node.end_byte].decode("utf8")
                    
                    # 파라미터 및 어노테이션 텍스트 추출
                    params_text = self._get_params_text(method_node, source)
                    
                    # 기존 _create_method를 사용하되 새 스키마 지원 확인 필요
                    # 이상적으로는 BaseFlowStrategy._create_method를 업데이트하거나 여기서 오버라이드해야 함.
                    # BaseFlowStrategy가 보이지 않으므로, args 맵 등을 전달할 수 있다고 가정.
                    # 사실 Java 전략은 커스텀 쿼리를 사용했으므로 여기서도 오버라이드하거나
                    # BaseFlowStrategy를 업데이트해야 함. 일단 일관성을 위해 Java 전략처럼 직접 쿼리 사용
                    
                    # 안전성과 Java와의 일관성을 위해 여기서 커스텀 생성 로직 구현
                    # 기본 메서드 호출을 대체하거나 검증 후 기본 메서드 사용.
                    # 제약 사항을 고려하여, 정확한 스키마 일치를 위해 Java 전략과 유사한 직접 DB 호출 사용.
                    
                    self._create_method_unified(method_name, method_name, file_path, n.start_point[0] + 1, method_source, params_text)
                    
        except Exception as e:
            logger.warning(f"Python method query error: {e}")

    def _get_params_text(self, function_node, source):
        params_node = function_node.child_by_field_name("parameters")
        if not params_node:
            return ""
        
        # 단순 추출: 파라미터 내부의 모든 텍스트
        # 또는 "a, b, c"와 같은 구조화된 리스트
        # Or structured list like "a, b, c"
        param_list = []
        for child in params_node.children:
            if child.type in ["identifier", "typed_parameter", "default_parameter", "typed_default_parameter"]:
                # 이름 추출
                p_text = source[child.start_byte:child.end_byte].decode("utf8")
                param_list.append(p_text)
        
        return ", ".join(param_list)

    def _create_method_unified(self, method_name, signature, file_path, line_number, source_code, args_text):
        # 참고: Python은 Java처럼 오버로딩이 없으므로 현재는 'method_name'을 시그니처로 사용.
        # 이상적으로는 메서드인 경우 클래스 경로를 포함해야 함.
        # 부모가 클래스인지 확인?
        
        # 클래스명에 대한 가벼운 문맥 확인이 좋겠지만 현재는 간단하게 유지.
        # 복잡한 노드 생성을 오버라이드함.
        
        query = """
        MATCH (f:FILE {path: $file_path})
        MERGE (m:METHOD {signature: $signature})
        SET m.name = $name,
            m.source = $source,
            m.args = $args,
            m.lineNumber = $line_number
        
        MERGE (f)-[:CONTAINS]->(m)
        MERGE (f)-[:AST]->(m)
        MERGE (f)-[:DEFINES]->(m)
        """
        
        # 참고: Java 전략은 CLASS->METHOD 연결. 여기 Python 전략은 FILE->METHOD 연결.
        # 클래스 내부라면 CLASS->METHOD를 연결해야 함.
        # 하지만 이번 리팩토링에서는 ArchitectureBuilder 순회 로직을 재작성하지 않고
        # 최소한의 연결성을 보장하기 위해 FILE->METHOD 유지를 선택.
        
        self.connector.execute_query(query, {
            "file_path": file_path,
            "signature": signature,
            "name": method_name,
            "source": source_code,
            "args": args_text,
            "line_number": line_number
        })

    def _extract_calls_python(self, node, source, file_path):
        from core.analysis.parser_factory import ParserFactory
        language = ParserFactory.get_language(".py")
        aggregated_calls = {} # (parent_name, target_name) -> count
        query_str = """
        (call
            function: [
                (identifier) @call.name
                (attribute attribute: (identifier) @call.method)
            ]
        )
        """
        try:
            query = language.query(query_str)
            captures = query.captures(node)
            for n, name in captures:
                call_name = source[n.start_byte:n.end_byte].decode("utf8")
                
                # 소스 연결을 위해 부모 메서드 찾기
                p = n.parent
                parent_method_name = None
                while p:
                    if p.type == "function_definition":
                        name_node = p.child_by_field_name("name")
                        if name_node:
                            parent_method_name = source[name_node.start_byte:name_node.end_byte].decode("utf8")
                        break
                    p = p.parent
                
                if parent_method_name:
                    key = (parent_method_name, call_name)
                    aggregated_calls[key] = aggregated_calls.get(key, 0) + 1

        except Exception as e:
            logger.warning(f"Python call query error: {e}")

        # 일괄 호출 생성
        for (parent, target), count in aggregated_calls.items():
            self._create_call_unified(parent, target, count)

    def _create_call_unified(self, source_method_signature, target_method_name, count):
        # Java 전략의 단순 연결과 유사
        query = """
        MATCH (m:METHOD {signature: $source})
        CREATE (c:CALL {methodName: $target, count: $count})
        MERGE (m)-[:HAS_CALL]->(c)
        """
        self.connector.execute_query(query, {
            "source": source_method_signature,
            "target": target_method_name,
            "count": count
        })
