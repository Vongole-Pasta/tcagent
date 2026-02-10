from infra.db_client import DBClient
import logging
import hashlib
import tree_sitter
import re
import os

logger = logging.getLogger(__name__)


class JavaFlowStrategy:
    """
    [Java 플로우 분석 전략]
    Java 소스 코드를 Tree-sitter로 파싱하여 구조와 호출 관계를 추출하는 클래스입니다.
    Spring Framework의 어노테이션(RequestMapping)을 인식하여 API 엔드포인트 정보도 함께 추출합니다.
    """
    def __init__(self, connector: DBClient):
        self.connector = connector
        # 자바에서 자주 쓰이는 Collection, Map 등의 제네릭 타입을 처리하기 위한 정규식
        self.generic_pattern = re.compile(r"<.*>")

    def process(self, tree: tree_sitter.Tree, source_code: bytes, file_path: str, scan_id: str = None):
        """
        [분석 실행 진입점]
        Tree-sitter 파싱 트리를 순회하며 패키지, 클래스, 메서드 정보를 추출합니다.
        
        Args:
            tree (tree_sitter.Tree): 파싱된 구문 트리
            source_code (bytes): 원본 소스 코드
            file_path (str): 파일 경로
            scan_id (str): 이번 분석 세션의 고유 아이디 (삭제된 노드 식별용)
        """
        root_node = tree.root_node
        
        # 1. 패키지 정보 추출
        package_name = self._get_package_name(root_node, source_code)
        
        # 2. 클래스/인터페이스 추출 (재귀 탐색)
        self._traverse_types(root_node, source_code, file_path, package_name, scan_id=scan_id)

    def _get_package_name(self, root_node, source_code):
        """[패키지명 추출] AST 루트에서 package 선언을 찾아 패키지명을 반환합니다."""
        for child in root_node.children:
            if child.type == "package_declaration":
                # package_declaration children: (scoped_identifier) or (identifier)
                for grandchild in child.children:
                    if grandchild.type in ["scoped_identifier", "identifier"]:
                        return source_code[grandchild.start_byte:grandchild.end_byte].decode("utf-8")
        return ""

    def _traverse_types(self, node, source_code: bytes, file_path: str, package_name: str, parent_class_name: str = "", scan_id: str = None):
        """[타입 재귀 탐색] 클래스, 인터페이스, Enum, Record 등 타입 선언을 찾아 처리합니다."""
        for child in node.children:
            if child.type in ["class_declaration", "interface_declaration", "enum_declaration", "record_declaration"]:
                self._process_type_declaration(child, source_code, file_path, package_name, parent_class_name, scan_id)
            
            # Inner class 처리를 위해 재귀 탐색은 필요한가? 
            # -> class_declaration 내부의 class_body 내부를 봐야 함.
            if child.type == "class_body":
                self._traverse_types(child, source_code, file_path, package_name, parent_class_name, scan_id)

    def _process_type_declaration(self, node, source_code: bytes, file_path: str, package_name: str, parent_name: str, scan_id: str = None):
        """
        [단일 타입 처리]
        발견된 타입을 DB에 TYPE 노드로 저장하고, 내부의 메서드를 추출합니다.
        Inner Class의 경우 부모 클래스 이름($ 구분자)을 포함하여 이름을 생성합니다.
        """
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
            
        class_name = source_code[name_node.start_byte:name_node.end_byte].decode("utf-8")
        
        # Unique TYPE Identity: Package + FileName(no_ext) + ClassName
        file_name_no_ext = os.path.splitext(os.path.basename(file_path))[0]
        full_name = f"{package_name}.{file_name_no_ext}.{class_name}" if package_name else f"{file_name_no_ext}.{class_name}"
        
        if parent_name:
            full_name = f"{parent_name}${class_name}" # Inner Class 컨벤션

        # 노드 생성: CLASS (Interface도 CLASS로 통합 관리하되 type 속성으로 구분)
        type_str = "CLASS"
        if node.type == "interface_declaration":
            type_str = "INTERFACE"
        elif node.type == "enum_declaration":
             type_str = "ENUM"
        
        # Docstring (Javadoc) 추출 - 보통 클래스 선언 직전의 comment
        # tree-sitter에서 comment는 형제 노드로 존재함. (바로 위)
        # 복잡하므로 일단 생략하거나 간단히 구현.
        
        # DB 저장
        self._create_type_node(full_name, class_name, package_name, type_str, file_path)
        
        # 메서드 추출을 위해 class_body 탐색
        body_node = node.child_by_field_name("body")
        if not body_node:
            for child in node.children:
                if child.type in ["class_body", "interface_body", "enum_body"]:
                    body_node = child
                    break
        
        if body_node:
            # Class Level Annotation (Base URL)
            base_url = self._extract_base_url(node, source_code)
            
            # Extract Fields first
            # Extract Fields first
            self._process_fields(body_node, source_code, full_name, file_path)
            
            # If Record, extract components as fields
            if node.type == "record_declaration":
                 self._process_record_components(node, source_code, full_name)
            
            # If Enum, extract constants as fields
            if node.type == "enum_declaration":
                 self._process_enum_constants(body_node, source_code, full_name)
            
            self._process_methods(body_node, source_code, full_name, file_path, scan_id, base_url)
            
            # Inner Class 재귀 호출
            self._traverse_types(body_node, source_code, file_path, package_name, full_name, scan_id)

    def _process_fields(self, class_body_node, source_code: bytes, class_full_name: str, file_path: str):
        """[필드 추출] 클래스 멤버 변수를 추출하여 FIELD 노드로 생성"""
        for child in class_body_node.children:
            if child.type == "field_declaration":
                # Type Parsing
                type_node = child.child_by_field_name("type")
                if not type_node: continue
                field_type = source_code[type_node.start_byte:type_node.end_byte].decode("utf-8")
                
                # Variable Declarator (could be multiple: int a, b;)
                for grandchild in child.children:
                    if grandchild.type == "variable_declarator":
                        name_node = grandchild.child_by_field_name("name")
                        if name_node:
                            field_name = source_code[name_node.start_byte:name_node.end_byte].decode("utf-8")
                            self._create_field_node(class_full_name, field_name, field_type)
            


    def _process_record_components(self, record_node, source_code: bytes, class_full_name: str):
        """[Record Component 추출] Record의 파라미터를 필드로 변환"""
        # structure: record_declaration -> formal_parameters -> formal_parameter -> (type, name)
        
        # 1. Find 'formal_parameters' child
        params_node = None
        for c in record_node.children:
            if c.type == "formal_parameters":
                 params_node = c
                 break
        
        if params_node:
            for param in params_node.children:
                if param.type == "formal_parameter":
                    # Inside formal_parameter: (type) (identifier)
                    f_type = None
                    f_name = None
                    
                    for grandchild in param.children:
                        # Name
                        if grandchild.type == "identifier":
                            f_name = source_code[grandchild.start_byte:grandchild.end_byte].decode("utf-8")
                        # Type (Anything else that looks like a type)
                        elif grandchild.type not in [",", "(", ")", "block_comment", "line_comment", "modifiers"]:
                            f_type = source_code[grandchild.start_byte:grandchild.end_byte].decode("utf-8")
                    
                    if f_name and f_type:
                        self._create_field_node(class_full_name, f_name, f_type) 

    def _process_enum_constants(self, enum_body_node, source_code: bytes, class_full_name: str):
        """[Enum Constant 추출] Enum 상수를 필드로 변환 (Type은 Enum 자신)"""
        # structure: enum_declaration -> enum_body -> enum_constant -> (name)
        
        for child in enum_body_node.children:
            if child.type == "enum_constant":
                name_node = child.child_by_field_name("name")
                if name_node:
                    constant_name = source_code[name_node.start_byte:name_node.end_byte].decode("utf-8")
                    
                    # Enum의 Type은 자기 자신
                    # 예: public enum Status { ACTIVE, INACTIVE } -> ACTIVE (Type: Status)
                    # class_full_name이 "com.example.Status"라면, Simple Type은 "Status"
                    
                    simple_type = class_full_name.split(".")[-1]
                    
                    # Create Field Node
                    self._create_field_node(class_full_name, constant_name, simple_type) 

    def _create_field_node(self, class_full_name, field_name, field_type):
        """
        [필드 노드 생성]
        TYPE -> CONTAINS -> FIELD
        FIELD -> OF_TYPE -> TYPE (Target Type)
        """
        # field_type (e.g., "List<String>", "UserDto") -> Simple Type for linking ("UserDto", "String")
        simple_type = self.generic_pattern.sub("", field_type)
        
        query = """
        MATCH (c:TYPE {fullName: $class_full_name})
        CREATE (f:FIELD {name: $field_name, type: $field_type}) // Always create new to avoid global merge
        MERGE (c)-[:CONTAINS]->(f)
        
        WITH f, $simple_type as targetTypeName
        // Try to link to Type if exists (Weak Link by Name)
        OPTIONAL MATCH (t:TYPE) WHERE t.name = targetTypeName
        FOREACH (_ IN CASE WHEN t IS NOT NULL THEN [1] ELSE [] END |
            MERGE (f)-[:OF_TYPE]->(t)
        )
        """
        # Note: Using simple name matching for now
        
        self.connector.execute_query(query, {
            "class_full_name": class_full_name,
            "field_name": field_name,
            "field_type": field_type,
            "simple_type": simple_type
        })


    def _create_type_node(self, full_name, name, package_name, type_str, file_path):
        query = """
        MERGE (c:TYPE {fullName: $full_name})
        SET c.name = $name,
            c.type = $type_str
        
        WITH c
        MATCH (f:FILE {path: $file_path})
        
        // Update File with package info
        SET f.package = $package_name
        
        MERGE (f)-[:CONTAINS]->(c)
        
        // Clean up old Fields to avoid duplication on re-analysis
        WITH c
        OPTIONAL MATCH (c)-[:CONTAINS]->(old_f:FIELD)
        DETACH DELETE old_f
        """
        self.connector.execute_query(query, {
            "full_name": full_name,
            "name": name,
            "package_name": package_name,
            "type_str": type_str,
            "file_path": file_path
        })

    def _process_methods(self, class_body_node, source_code: bytes, class_full_name: str, file_path: str, scan_id: str, base_url: str):
        for child in class_body_node.children:
            if child.type == "method_declaration" or child.type == "constructor_declaration":
                self._process_single_method(child, source_code, class_full_name, scan_id, base_url, file_path)

    def _extract_base_url(self, node, source_code: bytes):
        modifiers = node.child_by_field_name("modifiers")
        if not modifiers:
            # Fallback for tree-sitter-java: find parsing node by type
            for child in node.children:
                if child.type == "modifiers":
                    modifiers = child
                    break
        
        if not modifiers:
            return ""
        
        for child in modifiers.children:
            if child.type == "annotation" or child.type == "marker_annotation":
                name_node = child.child_by_field_name("name")
                if not name_node:
                    continue
                name_text = source_code[name_node.start_byte:name_node.end_byte].decode("utf-8")
                
                if "RequestMapping" in name_text:
                    return self._extract_annotation_value(child, source_code)
        return ""

    def _extract_annotation_value(self, node, source_code: bytes):
        args = node.child_by_field_name("arguments")
        if not args:
            return ""
        
        # 괄호 안의 내용 파싱 (@RequestMapping("/api") -> /api)
        # arguments 노드의 자식 중 string_literal 찾기
        for child in args.children:
            if child.type == "string_literal":
                return source_code[child.start_byte:child.end_byte].decode("utf-8").strip('"')
            elif child.type == "element_value_pair":
                # value="/api" 형태
                key = child.child_by_field_name("key")
                value = child.child_by_field_name("value")
                if key and value:
                    key_text = source_code[key.start_byte:key.end_byte].decode("utf-8")
                    if key_text == "value" or key_text == "path":
                         return source_code[value.start_byte:value.end_byte].decode("utf-8").strip('"')
        return ""

    def _process_single_method(self, method_node, source_code: bytes, class_full_name: str, scan_id: str, base_url: str, file_path: str):
        name_node = method_node.child_by_field_name("name")
        # structor의 경우 name이 메서드명과 동일
        if method_node.type == "constructor_declaration":
            # 생성자는 이름이 별도로 없고 클래스명과 동일 -> tree-sitter 구조 확인 필요
            # java parser에서 constructor_declaration의 name 필드는 클래스명을 가리킴
             pass
        
        # Fallback: Find identifier if field lookup fails (e.g. interface methods)
        if not name_node:
            for child in method_node.children:
                if child.type == "identifier":
                    name_node = child
                    break
        
        if not name_node:
            # print(f"DEBUG: Skipping method/constructor without name in {class_full_name}")
            return

        method_name = source_code[name_node.start_byte:name_node.end_byte].decode("utf-8")
        
        # 파라미터 리스트 추출 (Signature 생성을 위해 + PARAMETER 노드 생성)
        params_node = method_node.child_by_field_name("parameters")
        if not params_node:
             for child in method_node.children:
                 if child.type == "formal_parameters":
                     params_node = child
                     break
        
        param_list = []
        parameters_data = [] # List of dict: {name, type, index}
        
        if params_node:
            param_idx = 0
            for child in params_node.children:
                if child.type == "formal_parameter":
                    # Type + Name
                    p_type_node = child.child_by_field_name("type")
                    p_name_node = child.child_by_field_name("name")
                    
                    # Fallback for interface methods (no fields)
                    if not p_type_node or not p_name_node:
                         for p_child in child.children:
                             if p_child.type == "identifier":
                                 p_name_node = p_child
                             elif p_child.type not in ["modifiers", "marker_annotation", "annotation"] and (p_child.type.endswith("_type") or p_child.type == "type_identifier" or p_child.type == "generic_type" or p_child.type == "integral_type" or p_child.type == "boolean_type" or p_child.type == "floating_point_type" or p_child.type == "void_type"): 
                                 # This is a heuristic for type. 
                                 # Better approach: Iterate and pick non-identifier?
                                 # Let's match known type nodes or anything not identifier
                                 if not p_type_node: p_type_node = p_child

                    # Second Pass Fallback: simplistic "not identifier" is type
                    # (Similar to Record logic, but let's be careful with modifiers)
                    if not p_type_node:
                         for p_child in child.children:
                              if p_child.type not in ["identifier", "modifiers", "marker_annotation", "annotation", "spread_parameter", ",", "...", "line_comment", "block_comment"]:
                                   p_type_node = p_child
                                   
                    if p_type_node and p_name_node:
                        p_type = source_code[p_type_node.start_byte:p_type_node.end_byte].decode("utf-8")
                        p_name = source_code[p_name_node.start_byte:p_name_node.end_byte].decode("utf-8")
                        
                        # 제네릭 제거 (List<String> -> List) - 단순화 for Signature
                        p_type_simple = self.generic_pattern.sub("", p_type)
                        param_list.append(p_type_simple)
                        
                        parameters_data.append({
                            "name": p_name,
                            "type": p_type,
                            "index": param_idx
                        })
                        param_idx += 1
        
        # Signature: com.example.MyClass.myMethod(String,int)
        signature = f"{class_full_name}.{method_name}({','.join(param_list)})"
        
        # Source Code (Body 전체)
        # method_declaration 전체 텍스트
        full_source = source_code[method_node.start_byte:method_node.end_byte].decode("utf-8")
        
        # DB 저장
        # Hashing for Smart Update
        method_hash = hashlib.sha256(full_source.encode('utf-8')).hexdigest()
        
        # Endpoint Extraction
        endpoint = ""
        http_method = ""
        
        # Extract Method Annotations
        modifiers = method_node.child_by_field_name("modifiers")
        if not modifiers:
             # Fallback
            for child in method_node.children:
                if child.type == "modifiers":
                    modifiers = child
                    break

        if modifiers:
            for child in modifiers.children:
                 if child.type == "annotation" or child.type == "marker_annotation":
                    name_node = child.child_by_field_name("name")
                    if not name_node: continue
                    a_name = source_code[name_node.start_byte:name_node.end_byte].decode("utf-8")
                    
                    # Mapping Check
                    extracted_path = self._extract_annotation_value(child, source_code)
                    
                    if "GetMapping" in a_name:
                        http_method = "GET"
                        endpoint = self._combine_url(base_url, extracted_path)
                    elif "PostMapping" in a_name:
                        http_method = "POST"
                        endpoint = self._combine_url(base_url, extracted_path)
                    elif "PutMapping" in a_name:
                        http_method = "PUT"
                        endpoint = self._combine_url(base_url, extracted_path)
                    elif "DeleteMapping" in a_name:
                        http_method = "DELETE"
                        endpoint = self._combine_url(base_url, extracted_path)
                    elif "PatchMapping" in a_name:
                        http_method = "PATCH"
                        endpoint = self._combine_url(base_url, extracted_path)
                    elif "RequestMapping" in a_name:
                        http_method = "ALL" # or unknown
                        endpoint = self._combine_url(base_url, extracted_path)

        # DB 저장 (Updated Logic)
        self._create_method_node(signature, method_name, full_source, class_full_name, method_hash, scan_id, endpoint, http_method)
        
        # Create PARAMETER nodes
        for param in parameters_data:
            self._create_parameter_node(signature, param["name"], param["type"], param["index"])

        # Call 관계 추출 및 저장 (1단계: 텍스트 기반 호출 추출)
        # 메서드 바디(Body) 내부 탐색
        body_node = method_node.child_by_field_name("body")
        if body_node:
            calls = {} # Key: (methodName, objectName), Value: count
            self._extract_method_calls(body_node, source_code, signature, calls)
            
            for (target_name, obj_name), count in calls.items():
                self._create_call_node(signature, target_name, obj_name, count)

    def _create_parameter_node(self, method_signature, param_name, param_type, index):
        """
        [파라미터 노드 생성]
        METHOD -> CONTAINS -> PARAMETER
        PARAMETER -> OF_TYPE -> TYPE
        """
        simple_type = self.generic_pattern.sub("", param_type)
        
        query = """
        MATCH (m:METHOD {signature: $method_signature})
        CREATE (p:PARAMETER {name: $param_name, index: $index})  // CREATE new to avoid global merge
        
        MERGE (m)-[:CONTAINS]->(p)
        SET p.name = $param_name,
            p.type = $param_type,
            p.index = $index
        
        WITH p, $simple_type as targetTypeName
        OPTIONAL MATCH (t:TYPE) WHERE t.name = targetTypeName
        FOREACH (_ IN CASE WHEN t IS NOT NULL THEN [1] ELSE [] END |
            MERGE (p)-[:OF_TYPE]->(t)
        )
        """
        self.connector.execute_query(query, {
             "method_signature": method_signature,
             "param_name": param_name,
             "param_type": param_type,
             "index": index,
             "simple_type": simple_type
        })


    def _combine_url(self, base, path):
        if not base: base = ""
        if not path: path = ""
        base = base.rstrip("/")
        path = path.lstrip("/")
        return f"{base}/{path}"


    def _create_method_node(self, signature, name, source, class_full_name, method_hash, scan_id, endpoint, http_method):
        """
        [메서드 노드 생성 및 연결]
        추출된 메서드 정보를 그래프 DB에 'METHOD' 노드로 생성(MERGE)합니다.
        ...
        """
        query = """
        MERGE (m:METHOD {signature: $signature})
        
        ON CREATE SET 
            m.status = 'NEW'
            
        ON MATCH SET 
            m.status = CASE 
                WHEN m.hash = $method_hash THEN 'AS-IS' 
                ELSE 'MODIFIED' 
            END
        
        // Update Properties
        SET m.name = $name,
        m.source = $source,
        m.hash = $method_hash,
        m.last_scan_id = $scan_id,
        m.endpoint = $endpoint,
        m.http_method = $http_method
        
        WITH m
        MATCH (c:TYPE {fullName: $class_full_name})
        MERGE (c)-[:CONTAINS]->(m)
        
        // Clean up old Parameters to avoid duplication/globality
        WITH m
        OPTIONAL MATCH (m)-[:CONTAINS]->(old_p:PARAMETER)
        DETACH DELETE old_p
        """
        self.connector.execute_query(query, {
            "signature": signature,
            "name": name,
            "source": source,
            "class_full_name": class_full_name,
            "method_hash": method_hash,
            "scan_id": scan_id,
            "endpoint": endpoint,
            "http_method": http_method
        })


    def _extract_method_calls(self, node, source_code: bytes, caller_signature: str, calls: dict):
        # 재귀적으로 method_invocation 찾기
        for child in node.children:
            if child.type == "method_invocation":
                self._process_invocation(child, source_code, caller_signature, calls)
            
            # 재귀 진입 (단, class_declaration 등 중첩 클래스 정의는 제외해야 함)
            if child.type not in ["class_declaration", "interface_declaration", "method_declaration"]:
                 self._extract_method_calls(child, source_code, caller_signature, calls)

    def _process_invocation(self, invocation_node, source_code: bytes, caller_signature: str, calls: dict):
        # 구조: object.methodName(args)
        # object는 'expression' 필드, methodName은 'name' 필드
        
        obj_node = invocation_node.child_by_field_name("object")
        name_node = invocation_node.child_by_field_name("name")
        
        if not name_node:
            return
            
        method_name = source_code[name_node.start_byte:name_node.end_byte].decode("utf-8")
        
        # 1. 만약 obj_node가 있다면? (예: memberService.login)
        # -> 변수 이름을 통해 타입을 유추해야 함. (현재 심볼 테이블 부재로 인해 어려움)
        # -> 하지만 "변수명"이라도 저장하여 나중에 쿼리로 연결을 시도할 수 있게 함.
        
        obj_name = ""
        if obj_node:
            obj_name = source_code[obj_node.start_byte:obj_node.end_byte].decode("utf-8")
        
        # Aggregate call count
        key = (method_name, obj_name)
        calls[key] = calls.get(key, 0) + 1

    def _create_call_node(self, caller_signature, target_method_name, object_name, count):
        query = """
        MATCH (m:METHOD {signature: $caller_signature})
        CREATE (c:CALL {methodName: $target_method_name, count: $count})
        SET c.objectName = $object_name
        MERGE (m)-[:HAS_CALL]->(c)
        """
        self.connector.execute_query(query, {
            "caller_signature": caller_signature,
            "target_method_name": target_method_name,
            "object_name": object_name,
            "count": count
        })
