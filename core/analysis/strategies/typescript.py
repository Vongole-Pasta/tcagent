from .base import BaseFlowStrategy
import logging

logger = logging.getLogger(__name__)

class TypeScriptFlowStrategy(BaseFlowStrategy):
    def process(self, tree, source_code, file_path):
        self._extract_methods_ts(tree.root_node, source_code, file_path)
        # self._extract_controls_ts(tree.root_node, source_code, file_path) # REMOVED: Simplified Granularity
        self._extract_calls_ts(tree.root_node, source_code, file_path)

    def _extract_methods_ts(self, node, source, file_path):
        from core.analysis.parser_factory import ParserFactory
        language = ParserFactory.get_language(".ts") # 현재 TS/JS 모두 TS로 가정
        query_str = """
        (function_declaration name: (identifier) @method.name)
        (method_definition name: (property_identifier) @method.name)
        (variable_declarator name: (identifier) @var.name value: (arrow_function))
        """
        try:
            query = language.query(query_str)
            captures = query.captures(node)
            for n, name in captures:
                method_name = source[n.start_byte:n.end_byte].decode("utf8")
                method_node = n.parent
                if method_node.type == "variable_declarator":
                   method_source = source[method_node.start_byte:method_node.end_byte].decode("utf8")
                   # 변수에 할당된 화살표 함수의 경우, 파라미터는 화살표 함수 내부에 있음
                   # 구조: variable_declarator(name, value(arrow_function(parameters, body)))
                   arrow_func = method_node.child_by_field_name("value")
                   params_text = self._get_params_text_ts(arrow_func, source)
                else: 
                   method_source = source[method_node.start_byte:method_node.end_byte].decode("utf8")
                   params_text = self._get_params_text_ts(method_node, source)
                   
                # 통합 생성 (Unified Creation)
                self._create_method_unified(method_name, method_name, file_path, n.start_point[0] + 1, method_source, params_text)
                
        except Exception as e:
             logger.warning(f"TS flow query error: {e}")

    def _get_params_text_ts(self, function_node, source):
        if not function_node: return ""
        params_node = function_node.child_by_field_name("parameters")
        if not params_node:
            return ""
        
        # 파라미터의 텍스트 표현 추출
        # 더 깔끔하게 하려면 타입을 제거하고 반복할 수 있지만, 지금은 원본 텍스트도 괜찮음
        # 로직: 가능하면 파라미터 이름만 가져옴
        
        param_list = []
        for child in params_node.children:
            p_text = ""
            if child.type == "identifier":
                 p_text = source[child.start_byte:child.end_byte].decode("utf8")
            elif child.type in ["required_parameter", "optional_parameter"]:
                 pattern = child.child_by_field_name("pattern")
                 if pattern:
                     p_text = source[pattern.start_byte:pattern.end_byte].decode("utf8")
            
            if p_text:
                param_list.append(p_text)
                
        return ", ".join(param_list)

    def _create_method_unified(self, method_name, signature, file_path, line_number, source_code, args_text):
        query = """
        MATCH (f:FILE {path: $file_path})
        MERGE (m:METHOD {signature: $signature})
        SET m.name = $name,
            m.source = $source,
            m.args = $args,
            m.lineNumber = $line_number
        
        MERGE (f)-[:CONTAINS]->(m)
        """
        self.connector.execute_query(query, {
            "file_path": file_path,
            "signature": signature,
            "name": method_name,
            "source": source_code,
            "args": args_text,
            "line_number": line_number
        })

    def _extract_calls_ts(self, node, source, file_path):
        from core.analysis.parser_factory import ParserFactory
        language = ParserFactory.get_language(".ts")
        aggregated_calls = {} # (parent_name, target_name) -> count
        query_str = """
        (call_expression
            function: [
                (identifier) @call.name
                (member_expression property: (property_identifier) @call.method)
            ]
        )
        """
        try:
            query = language.query(query_str)
            captures = query.captures(node)
            for n, name in captures:
                call_name = source[n.start_byte:n.end_byte].decode("utf8")
                parent_method_name = self._find_parent_method_ts(n, source)
                
                if parent_method_name:
                     key = (parent_method_name, call_name)
                     aggregated_calls[key] = aggregated_calls.get(key, 0) + 1

        except Exception as e:
             logger.warning(f"TS call query error: {e}")

        # 일괄 호출 생성
        for (parent, target), count in aggregated_calls.items():
            self._create_call_unified(parent, target, count)

    def _find_parent_method_ts(self, node, source):
        # ... logic same as before ... 
        p = node.parent
        while p:
            if p.type == "function_declaration":
                name_node = p.child_by_field_name("name")
                if name_node:
                    return source[name_node.start_byte:name_node.end_byte].decode("utf8")
                break
            elif p.type == "method_definition":
                name_node = p.child_by_field_name("name")
                if name_node:
                    return source[name_node.start_byte:name_node.end_byte].decode("utf8")
                break
            elif p.type == "variable_declarator":
                val_node = p.child_by_field_name("value")
                if val_node and val_node.type in ["arrow_function", "function_expression"]:
                    name_node = p.child_by_field_name("name")
                    if name_node:
                        return source[name_node.start_byte:name_node.end_byte].decode("utf8")
                    break
            p = p.parent
        return None

    def _create_call_unified(self, source_method_signature, target_method_name, count):
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
