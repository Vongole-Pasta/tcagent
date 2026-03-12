"""
순수 Java AST 파싱 모듈.
tree-sitter를 사용하여 Java 소스 코드에서 타입, 메서드, 필드, 호출 관계를 추출합니다.
DB 의존성 없음 — 파싱 결과는 store/models.py의 dataclass로 반환됩니다.
"""
import hashlib
import logging
import re

from tree_sitter_language_pack import get_parser

from core.analysis.store.models import (
    TypeInfo, ParamInfo, ConstantInfo,
    ParsedType, ParsedField, ParsedMethod, ParsedFileResult,
    ParsedCallEdge, ParsedParameterEdge, ParsedReturnEdge,
)

logger = logging.getLogger(__name__)

# HAS_PARAMETER / RETURNS 엣지 생성 대상에서 제외할 기본형·표준 타입
_PRIMITIVE_TYPES = {
    "String", "int", "long", "short", "byte", "char",
    "float", "double", "boolean",
    "Integer", "Long", "Short", "Byte", "Character",
    "Float", "Double", "Boolean",
    "void", "Object", "List", "Map", "Set",
    "ArrayList", "HashMap", "HashSet",
    "Optional", "Stream",
}


class JavaParser:
    """
    [Java AST 파서]
    Tree-sitter 파싱 트리를 순회하며 구조와 호출 관계를 추출합니다.
    Side effect 없음 — 결과는 ParsedFileResult로 반환됩니다.
    """

    # 소스 루트 탐지 패턴 (우선순위 순)
    # 패턴 앞의 마지막 세그먼트 = 모듈명, 패턴 뒤 = 패키지/소스 경로
    # 예: backend/user-service/src/main/java/com/ex/A.java
    #     → 모듈명: user-service, 패키지 경로: com/ex/A.java
    ROOT_PATTERNS: list[str] = [
        "src/main/java/",
        "src/",
    ]

    _ts_parser = get_parser("java")

    def __init__(self):
        self.generic_pattern = re.compile(r"<.*>")
        self.type_split_pattern = re.compile(r"[<>, \t]+")

    # -----------------------------------------------------------------------
    # 진입점
    # -----------------------------------------------------------------------
    def parse(self, source_code: bytes, file_path: str, scan_id: str | None = None) -> ParsedFileResult:
        """
        tree-sitter java parser가 파일을 파싱한 결과로 얻은 AST 트리를 순회탐색하면서
        공통으로 정의한 스키마에 맞게 관계를 추출합니다.

        Args:
            source_code: 원본 소스 코드
            file_path: 파일 경로
            scan_id: 이번 분석 세션의 고유 아이디 (삭제된 노드 식별용)

        Returns:
            ParsedFileResult: 파싱 결과 (타입, 메서드, 필드, 호출 등)
        """
        result = ParsedFileResult()
        tree = self._ts_parser.parse(source_code)
        root_node = tree.root_node

        package_name = self._get_package_name(root_node, source_code)
        imports, wildcard_imports = self._extract_imports(root_node, source_code)

        # 파일 레벨 컨텍스트 저장 (EdgeLinker가 타입 해석 시 참조)
        result.package_name = package_name
        result.imports = imports
        result.wildcard_imports = wildcard_imports

        self._traverse_types(root_node, source_code, file_path, package_name, result, scan_id=scan_id)

        return result

    # -----------------------------------------------------------------------
    # 패키지명 추출(qualname 지정을 위해)
    # -----------------------------------------------------------------------
    def _get_package_name(self, root_node, source_code):
        """AST 루트에서 package 선언을 찾아 패키지명을 반환합니다."""
        for child in root_node.children:
            if child.type == "package_declaration":
                for grandchild in child.children:
                    if grandchild.type in ["scoped_identifier", "identifier"]:
                        return source_code[grandchild.start_byte:grandchild.end_byte].decode("utf-8")
        return ""

    # -----------------------------------------------------------------------
    # import 추출
    # -----------------------------------------------------------------------
    def _extract_imports(self, root_node, source_code: bytes) -> tuple[list[str], list[str]]:
        """
        import 선언을 추출합니다.

        Returns:
            (imports, wildcard_imports) 튜플
            - imports: 정규 import 목록 (예: ["com.example.model.User"])
            - wildcard_imports: 와일드카드 import의 패키지명 (예: ["com.example.util"])
                → "com.example.util.*" 에서 ".*" 제거한 패키지명
        """
        imports = []
        wildcard_imports = []

        for child in root_node.children:
            if child.type != "import_declaration":
                continue

            # static import는 메서드 import이므로 스킵
            has_static = any(c.type == "static" for c in child.children)
            if has_static:
                continue

            # asterisk(*) 존재 여부로 와일드카드 판별
            has_asterisk = any(
                c.type == "asterisk" or source_code[c.start_byte:c.end_byte] == b"*"
                for c in child.children
            )

            # scoped_identifier 또는 identifier에서 패키지/클래스명 추출
            for gc in child.children:
                if gc.type in ["scoped_identifier", "identifier"]:
                    import_path = source_code[gc.start_byte:gc.end_byte].decode("utf-8")
                    if has_asterisk:
                        wildcard_imports.append(import_path)
                    else:
                        imports.append(import_path)
                    break

        return imports, wildcard_imports

    # -----------------------------------------------------------------------
    # 타입 처리
    # -----------------------------------------------------------------------
    def _traverse_types(self, node, source_code: bytes, file_path: str, package_name: str,
                        result: ParsedFileResult, parent_class_name: str = "", scan_id: str | None = None):
        """클래스, 인터페이스, Enum, Record 등 타입 선언을 찾아 처리합니다."""
        for child in node.children:
            if child.type in ["class_declaration", "interface_declaration", "enum_declaration", "record_declaration"]:
                self._process_type(child, source_code, file_path, package_name,
                                               result, parent_class_name, scan_id)
            if child.type == "class_body":
                self._traverse_types(child, source_code, file_path, package_name,
                                     result, parent_class_name, scan_id)

    def _process_type(self, node, source_code: bytes, file_path: str, package_name: str,
                                  result: ParsedFileResult, parent_name: str, scan_id: str | None = None):
        """발견된 타입 정보를 ParsedType으로 수집하고, 내부를 재귀적으로 탐색합니다."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        class_name = source_code[name_node.start_byte:name_node.end_byte].decode("utf-8")

        # TYPE.qualname 조립 (패키지명.클래스명)
        qualname = f"{package_name}.{class_name}" if package_name else class_name
        if parent_name: # 내부 클래스인 경우, 뒤에 $와 함께 붙입니다.
            qualname = f"{parent_name}${class_name}"

        # TYPE.kind 판단
        match node.type:
            case "interface_declaration":   kind = "INTERFACE"
            case "enum_declaration":        kind = "ENUM"
            case "record_declaration":      kind = "RECORD"
            case _:                         kind = "CLASS"

        # TYPE.constants 추출 (Enum 상수)
        constants: list[ConstantInfo] = []
        if kind == "ENUM":
            body_for_enum = node.child_by_field_name("body")
            if body_for_enum:
                constants = self._extract_enum_constants(body_for_enum, source_code)

        # TYPE.supertypes 추출 (extends + implements 통합)
        supertypes = self._extract_supertypes(node, source_code)

        # ParsedType으로 result.types에 추가
        result.types.append(ParsedType(
            qualname=qualname,
            name=class_name,
            kind=kind,
            file_path=file_path,
            constants=constants,
            supertypes=supertypes,
        ))

        # 클래스 body 부분 탐색
        body_node = node.child_by_field_name("body_node")
        if not body_node:
            for child in node.children:
                if child.type in ["class_body", "interface_body", "enum_body"]:
                    body_node = child
                    break

        # 먼저 Record의 컴포넌트(파라미터로 선언됨)를 FIELD로 변환
        if kind == "RECORD":
            self._process_record(node, source_code, qualname, result)

        # body_node가 존재하면 필드/메서드 추출과 내부 클래스 재귀 탐색을 수행합니다.
        if body_node:
            # 필드 추출
            self._process_field(body_node, source_code, qualname, result)

            # 메서드 추출
            base_uri = self._extract_base_uri(node, source_code) # Controller 클래스에 공통 선언된 URI 추출
            self._process_method(body_node, source_code, qualname, result, scan_id, base_uri)

            # Inner Class 재귀 호출
            self._traverse_types(body_node, source_code, file_path, package_name,
                                result, qualname, scan_id)

    # -----------------------------------------------------------------------
    # 바디 멤버 순회 유틸리티
    # -----------------------------------------------------------------------
    def _iter_body_members(self, body_node):
        """클래스/enum 바디의 멤버 노드를 순회합니다.
        enum의 경우 필드/메서드/생성자가 enum_body_declarations 안에 있으므로,
        해당 노드 내부까지 한 레벨 더 탐색합니다."""
        for child in body_node.children:
            if child.type == "enum_body_declarations":
                yield from child.children
            else:
                yield child

    # -----------------------------------------------------------------------
    # 필드 처리
    # -----------------------------------------------------------------------
    def _process_field(self, class_body_node, source_code: bytes, type_qualname: str, result: ParsedFileResult):
        """클래스 바디에서 field_declaration 노드를 찾아 ParsedField로 수집합니다."""
        for child in self._iter_body_members(class_body_node):
            if child.type == "field_declaration":
                # 타입 추출
                type_node = child.child_by_field_name("type")
                if not type_node:
                    continue
                field_type_str = source_code[type_node.start_byte:type_node.end_byte].decode("utf-8")
                field_type = self._build_typeinfo(field_type_str)

                # 제약조건(어노테이션) 추출
                constraint = self._extract_annotations(child, source_code)

                # 변수 선언자 처리 (int a, b; 같은 다중 선언도 경우의 수에 포함)
                for declarator in child.children:
                    if declarator.type == "variable_declarator":
                        name_node = declarator.child_by_field_name("name")
                        if name_node:
                            field_name = source_code[name_node.start_byte:name_node.end_byte].decode("utf-8")
                            result.fields.append(ParsedField(
                                qualname=f"{type_qualname}.{field_name}",
                                type_qualname=type_qualname,
                                name=field_name,
                                field_type=field_type,
                                constraint=constraint,
                            ))

    # RECORD 처리 (다른 kind와 생긴 게 달라서 처리 방식도 다릅니다.)
    def _process_record(self, record_node, source_code: bytes, type_qualname: str, result: ParsedFileResult):
        """
        Record의 컴포넌트(파라미터)를 필드로 변환합니다.
        java 레코드 구조가 public record User(String name, int age) { ... } 같은 형태라,
        → User.name, User.age 같이 FIELD 노드로 변환합니다.
        """
        params_node = None
        for child in record_node.children:
            if child.type == "formal_parameters":
                params_node = child
                break

        if not params_node:
            return

        for param in params_node.children:
            if param.type == "formal_parameter":
                type_node = None
                name_node = None
                for grandchild in param.children:
                    if grandchild.type == "identifier":
                        name_node = grandchild
                    elif grandchild.type not in [",", "(", ")", "block_comment", "line_comment", "modifiers"]:
                        type_node = grandchild

                if name_node and type_node:
                    field_name = source_code[name_node.start_byte:name_node.end_byte].decode("utf-8")
                    field_type_str = source_code[type_node.start_byte:type_node.end_byte].decode("utf-8")
                    # Record 파라미터의 어노테이션을 constraint로 추출 (예: @NotBlank @Email)
                    constraint = self._extract_annotations(param, source_code)
                    result.fields.append(ParsedField(
                        qualname=f"{type_qualname}.{field_name}",
                        type_qualname=type_qualname,
                        name=field_name,
                        field_type=self._build_typeinfo(field_type_str),
                        constraint=constraint,
                    ))

    # 애노테이션 처리 (FIELD.constraint, METHOD.params.annotation 등)
    def _extract_annotations(self, node, source_code: bytes) -> str:
        """
        노드의 modifiers에서 어노테이션을 추출합니다. 
        (예: "@NotBlank(message="....")", "@PathVariable(value="xxx")" 등)
        """
        modifiers_node = node.child_by_field_name("modifiers")
        # formal_parameter 등 일부 노드는 modifiers가 named field가 아니므로 children 순회 fallback
        if not modifiers_node:
            for child in node.children:
                if child.type == "modifiers":
                    modifiers_node = child
                    break
        if not modifiers_node:
            return ""

        annotations = []
        for child in modifiers_node.children:
            if child.type in ["annotation", "marker_annotation"]:
                annotations.append(
                    source_code[child.start_byte:child.end_byte].decode("utf-8")
                )

        return " ".join(annotations) if annotations else ""

    # 상위 타입 추출 (extends + implements → supertypes 통합)
    def _extract_supertypes(self, node, source_code: bytes) -> list[str]:
        """
        클래스/인터페이스의 상위 타입(extends + implements)을 추출합니다.
        Java의 extends(단일/다중) + implements를 합쳐 supertypes 리스트로 반환합니다.

        Returns:
            상위 타입 이름 목록 (제네릭 제거된 단순 이름)
        """
        supertypes = []

        # extends 추출 (class → 단일 상속, interface → 다중 extends)
        superclass_node = node.child_by_field_name("superclass")
        if superclass_node:
            self._collect_type_names(superclass_node, source_code, supertypes)

        # implements 추출
        interfaces_node = node.child_by_field_name("interfaces")
        if interfaces_node:
            self._collect_type_names(interfaces_node, source_code, supertypes)

        # 인터페이스의 extends (다른 인터페이스를 extends하는 경우)
        if node.type == "interface_declaration":
            extends_node = node.child_by_field_name("extends_interfaces")
            if extends_node:
                self._collect_type_names(extends_node, source_code, supertypes)

        return supertypes

    def _collect_type_names(self, node, source_code: bytes, out: list[str]):
        """AST 노드에서 타입 이름들을 추출하여 out 리스트에 추가합니다."""
        for child in node.children:
            if child.type in ["type_identifier", "scoped_type_identifier", "generic_type"]:
                raw = source_code[child.start_byte:child.end_byte].decode("utf-8")
                out.append(self.generic_pattern.sub("", raw))
            elif child.type == "type_list":
                self._collect_type_names(child, source_code, out)

    # -----------------------------------------------------------------------
    # 메서드 처리
    # -----------------------------------------------------------------------
    def _process_method(self, class_body_node, source_code: bytes, class_qualname: str, result: ParsedFileResult, scan_id: str | None, base_uri: str):
        """클래스 바디에서 method_declaration/constructor_declaration을 찾아 처리합니다."""
        for child in self._iter_body_members(class_body_node):
            if child.type in ["method_declaration", "constructor_declaration"]:
                self._process_each_method(child, source_code, class_qualname, result, scan_id, base_uri)

    # 각 메서드 처리
    def _process_each_method(self, method_node, source_code: bytes, class_qualname: str, result: ParsedFileResult, scan_id: str | None, base_uri: str):
        """하나의 메서드/생성자를 ParsedMethod로 수집합니다."""
        name_node = method_node.child_by_field_name("name")
        if not name_node:
            for child in method_node.children:
                if child.type == "identifier":
                    name_node = child
                    break
        if not name_node:
            return

        # METHOD.name 추출
        method_name = source_code[name_node.start_byte:name_node.end_byte].decode("utf-8")

        # METHOD.source 추출 (메서드 전체 소스 코드)
        source = source_code[method_node.start_byte:method_node.end_byte].decode("utf-8")

        # METHOD.signature 추출 (선언부만, body 제외)
        signature = self._extract_signature(method_node, source_code)

        # METHOD.endpoint_uri 추출 (REST 엔드포인트 정보)
        endpoint_uri, http_method = self._extract_endpoint_info(method_node, source_code, base_uri)

        # METHOD.hash 계산 (시그니처 + 바디 전체)
        hash = hashlib.sha256(source.encode("utf-8")).hexdigest()

        # METHOD.params 추출 (ParamInfo 리스트 + qualname 조립용 타입명 리스트)
        params, param_types = self._extract_params(method_node, source_code)

        # METHOD.return_type 추출 (생성자는 None)
        return_type = self._extract_return_type(method_node, source_code)

        # METHOD.qualname 조립 (패키지명.클래스명.함수이름(매개변수 타입, ..))
        qualname = f"{class_qualname}.{method_name}({','.join(param_types)})"

        # METHOD.local_vars 추출 (로컬 변수 타입 맵 — EdgeLinker가 호출 해석 시 참조)
        local_vars, unresolved_vars = self._extract_local_vars(method_node, source_code)

        # ParsedMethod로 result.methods에 추가
        result.methods.append(ParsedMethod(
            qualname=qualname,
            name=method_name,
            source=source,
            class_qualname=class_qualname,
            signature=signature,
            params=params,
            return_type=return_type,
            method_hash=hash,
            scan_id=scan_id,
            endpoint_uri=endpoint_uri,
            http_method=http_method,
            local_vars=local_vars,
            unresolved_vars=unresolved_vars,
        ))

        # --- 엣지 정보 수집 ---
        self._collect_call_edges(method_node, source_code, qualname, result)
        self._collect_parameter_edges(params, qualname, result)
        self._collect_return_edge(return_type, qualname, result)

    # -----------------------------------------------------------------------
    # 로컬 변수 타입 맵 추출
    # -----------------------------------------------------------------------

    def _extract_local_vars(
        self, method_node, source_code: bytes,
    ) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
        """
        메서드 바디의 local_variable_declaration에서 로컬 변수 타입 정보를 추출합니다.

        Returns:
            (local_vars, unresolved_vars) 튜플
            - local_vars: 타입이 확정된 변수 {변수명 → 타입명}
            - unresolved_vars: 메서드 리턴타입 추론 필요 {변수명 → (메서드명, 객체명)}
        """
        body_node = method_node.child_by_field_name("body")
        if not body_node:
            return {}, {}

        local_vars: dict[str, str] = {}
        unresolved_vars: dict[str, tuple[str, str]] = {}
        self._scan_local_vars(body_node, source_code, local_vars, unresolved_vars)
        return local_vars, unresolved_vars

    def _scan_local_vars(
        self, node, source_code: bytes,
        local_vars: dict[str, str],
        unresolved_vars: dict[str, tuple[str, str]],
    ):
        """AST를 재귀 순회하며 지역 변수 선언을 수집합니다."""
        for child in node.children:
            if child.type == "local_variable_declaration":
                type_node = child.child_by_field_name("type")
                if not type_node:
                    continue
                type_str = source_code[type_node.start_byte:type_node.end_byte].decode("utf-8")
                # var 키워드 → 우변 패턴에 따라 타입 추론 시도
                if type_str == "var":
                    self._infer_var_types(child, source_code, local_vars, unresolved_vars)
                    continue
                # 제네릭 제거한 단순 타입명 (예: List<Member> → List)
                simple_type = self.generic_pattern.sub("", type_str)
                for decl in child.children:
                    if decl.type == "variable_declarator":
                        name_node = decl.child_by_field_name("name")
                        if name_node:
                            var_name = source_code[name_node.start_byte:name_node.end_byte].decode("utf-8")
                            local_vars[var_name] = simple_type
            # 내부 클래스/람다 선언은 일단 진입하지 않음
            elif child.type not in ("class_declaration", "lambda_expression"):
                self._scan_local_vars(child, source_code, local_vars, unresolved_vars)

    def _infer_var_types(
        self, decl_node, source_code: bytes,
        local_vars: dict[str, str],
        unresolved_vars: dict[str, tuple[str, str]],
    ):
        """
        var 타입으로 된 지역변수의 타입을 추론합니다.
        1. 가능한 케이스: 
        인스턴스 구문인 경우 (var a = new Type();) → local_vars에 저장
        2. 추가작업이 필요한 케이스:
        함수호출인 경우 (var a = obj.foo();) → unresolved_vars에 저장 
        (EdgeLinker가 함수 호출의 리턴 타입을 가지고 해석)
        """
        for decl in decl_node.children:
            if decl.type != "variable_declarator":
                continue
            name_node = decl.child_by_field_name("name")
            value_node = decl.child_by_field_name("value")
            if not name_node or not value_node:
                continue
            var_name = source_code[name_node.start_byte:name_node.end_byte].decode("utf-8")

            if value_node.type == "object_creation_expression":
                # new Type<...>() → 타입 즉시 확정
                creation_type = value_node.child_by_field_name("type")
                if not creation_type:
                    continue
                type_str = source_code[creation_type.start_byte:creation_type.end_byte].decode("utf-8")
                local_vars[var_name] = self.generic_pattern.sub("", type_str)

            elif value_node.type == "method_invocation":
                # obj.method() / method() → EdgeLinker에서 리턴타입 해석 필요
                method_name_node = value_node.child_by_field_name("name")
                obj_node = value_node.child_by_field_name("object")
                if not method_name_node:
                    continue
                method_name = source_code[method_name_node.start_byte:method_name_node.end_byte].decode("utf-8")
                obj_name = ""
                if obj_node and obj_node.type != "method_invocation":
                    obj_name = source_code[obj_node.start_byte:obj_node.end_byte].decode("utf-8")
                unresolved_vars[var_name] = (method_name, obj_name)

    # -----------------------------------------------------------------------
    # 엣지 수집
    # -----------------------------------------------------------------------

    def _collect_call_edges(
        self, method_node, source_code: bytes, qualname: str, result: ParsedFileResult,
    ):
        """CALLS 엣지: 메서드 바디에서 호출 관계를 추출합니다."""
        body_node = method_node.child_by_field_name("body")
        if not body_node:
            return
        calls: list[tuple[str, str, int, list[str], list[str], str]] = []
        self._extract_method_calls(body_node, source_code, calls)
        for target_name, obj_name, arg_count, arg_hints, recv_chain, recv_object in calls:
            result.calls.append(ParsedCallEdge(
                caller_qualname=qualname,
                target_method_name=target_name,
                object_name=obj_name,
                arg_count=arg_count,
                arg_hints=arg_hints,
                receiver_chain=recv_chain,
                receiver_object=recv_object,
            ))

    def _collect_parameter_edges(
        self, params: list, qualname: str, result: ParsedFileResult,
    ):
        """HAS_PARAMETER 엣지: 사용자 정의 타입을 가진 파라미터만 수집합니다."""
        for param in params:
            if any(not self._is_primitive_type(t) for t in param["type"]["layout"]):
                result.parameter_edges.append(ParsedParameterEdge(
                    method_qualname=qualname,
                    param_info=param,
                ))

    def _collect_return_edge(
        self, return_type, qualname: str, result: ParsedFileResult,
    ):
        """RETURNS 엣지: 사용자 정의 타입을 포함한 리턴 타입만 수집합니다."""
        if return_type and return_type["layout"]:
            if any(not self._is_primitive_type(t) for t in return_type["layout"]):
                result.return_edges.append(ParsedReturnEdge(
                    method_qualname=qualname,
                    return_info=return_type,
                ))

    # -----------------------------------------------------------------------
    # CALLS 엣지 추출 (내부)
    # -----------------------------------------------------------------------

    def _extract_method_calls(self, node, source_code: bytes, calls: list):
        """AST를 재귀 순회하며 메서드 호출(method_invocation)과 메서드 참조(method_reference)를 수집합니다."""
        for child in node.children:
            if child.type == "method_invocation":
                self._process_invocation(child, source_code, calls)
            elif child.type == "method_reference": # :: 로 참조되는 메서드 감지
                self._process_method_reference(child, source_code, calls)
            # 내부 클래스/메서드 선언은 별도 스코프이므로 진입하지 않음
            if child.type not in ("class_declaration", "interface_declaration", "method_declaration"):
                self._extract_method_calls(child, source_code, calls)

    def _process_invocation(self, invocation_node, source_code: bytes, calls: list):
        """
        하나의 method_invocation 노드에서 호출 정보를 추출합니다.
        체이닝은 AST를 재귀적으로 언와인딩하여 무한 뎁스까지 추적합니다.

        예: a.getUser().getAddress().getCity()
          AST: method_invocation(method_invocation(method_invocation(a, getUser), getAddress), getCity)
          → receiver_chain=["getUser", "getAddress"], receiver_object="a", target="getCity"
        """
        obj_node = invocation_node.child_by_field_name("object")
        name_node = invocation_node.child_by_field_name("name")
        if not name_node:
            return

        method_name = source_code[name_node.start_byte:name_node.end_byte].decode("utf-8")

        # 인자 개수 + 인자 타입 힌트 추출
        args_node = invocation_node.child_by_field_name("arguments")
        arg_count = self._count_arguments(args_node) if args_node else 0
        arg_hints = self._extract_arg_hints(args_node, source_code) if args_node else []

        obj_name = ""
        receiver_chain: list[str] = []
        receiver_object = ""

        if obj_node:
            if obj_node.type == "method_invocation":
                # 체이닝: AST를 루트까지 재귀적으로 언와인딩
                receiver_object, receiver_chain = self._unwind_chain(obj_node, source_code)
            else:
                obj_name = source_code[obj_node.start_byte:obj_node.end_byte].decode("utf-8")

        calls.append((method_name, obj_name, arg_count, arg_hints, receiver_chain, receiver_object))

    def _unwind_chain(self, invocation_node, source_code: bytes) -> tuple[str, list[str]]:
        """
        체이닝된 method_invocation AST를 루트까지 재귀적으로 언와인딩합니다.

        예: a.getUser().getAddress() (이것이 getCity()의 obj_node)
          → ("a", ["getUser", "getAddress"])

        Returns:
            (root_object, chain) 튜플
            - root_object: 체이닝의 루트 객체명 (예: "a")
            - chain: 메서드 호출 순서 (루트→말단). 예: ["getUser", "getAddress"]
        """
        chain: list[str] = []
        current = invocation_node

        # method_invocation을 따라 올라가며 메서드명 수집
        while current and current.type == "method_invocation":
            name_node = current.child_by_field_name("name")
            if name_node:
                chain.append(source_code[name_node.start_byte:name_node.end_byte].decode("utf-8"))
            current = current.child_by_field_name("object")

        # current는 체이닝의 루트 (identifier, field_access 등)
        root_object = ""
        if current:
            root_object = source_code[current.start_byte:current.end_byte].decode("utf-8")

        # chain은 말단→루트 순으로 수집되었으므로 뒤집어서 루트→말단 순으로
        chain.reverse()
        return root_object, chain

    def _process_method_reference(self, ref_node, source_code: bytes, calls: list):
        """
        메서드 참조(::) 노드에서 호출 정보를 추출합니다.
        예: Member::recordLoginFailure, this::toResponse, ProductDto.Response::from
        AST 구조: method_reference → identifier(객체) :: identifier(메서드)
        """
        # :: 기준 왼쪽(객체/타입)과 오른쪽(메서드명) 추출
        # tree-sitter에서 method_reference의 children: [object, "::", name]
        obj_text = ""
        method_name = ""
        for child in ref_node.children:
            if child.type == "::":
                continue
            # 마지막 identifier가 메서드명, 그 앞이 객체/타입
            if not method_name and not obj_text:
                obj_text = source_code[child.start_byte:child.end_byte].decode("utf-8")
            elif obj_text and not method_name:
                method_name = source_code[child.start_byte:child.end_byte].decode("utf-8")

        if not method_name:
            return

        # this 참조는 obj_name 비워둠 (자기 클래스 내부 호출)
        if obj_text == "this":
            obj_text = ""

        calls.append((method_name, obj_text, 0, [], [], ""))

    def _count_arguments(self, args_node) -> int:
        """argument_list 노드에서 인자 개수를 셉니다."""
        count = 0
        for child in args_node.children:
            # 괄호와 쉼표를 제외한 자식 노드가 인자
            if child.type not in ["(", ")", ","]:
                count += 1
        return count

    # 리터럴 노드 타입 → Java 타입 매핑
    _LITERAL_TYPE_MAP = {
        "string_literal":                    "String",
        "decimal_integer_literal":           "int",
        "hex_integer_literal":               "int",
        "octal_integer_literal":             "int",
        "binary_integer_literal":            "int",
        "decimal_floating_point_literal":    "double",
        "hex_floating_point_literal":        "double",
        "character_literal":                 "char",
        "true":                              "boolean",
        "false":                             "boolean",
        "null_literal":                      "",       # null은 모든 참조 타입과 호환 → 빈 힌트
    }

    def _extract_arg_hints(self, args_node, source_code: bytes) -> list[str]:
        """
        argument_list의 각 인자에서 타입 힌트를 추출합니다.
        오버로딩 구분 시 EdgeLinker가 사용합니다.

        힌트 종류:
          - identifier: 변수명 그대로 (EdgeLinker가 local_vars/params/fields에서 타입 해석)
          - 리터럴: Java 타입명으로 변환 ("String", "int", "boolean" 등)
          - new Type(): 타입명 추출
          - cast (Type) x: 타입명 추출
          - 그 외 (메서드호출, 이항식 등): "" (해석 불가)
        """
        hints: list[str] = []
        for child in args_node.children:
            if child.type in ("(", ")", ","):
                continue
            hints.append(self._arg_hint_for_node(child, source_code))
        return hints

    def _arg_hint_for_node(self, node, source_code: bytes) -> str:
        """단일 인자 노드에서 타입 힌트를 추출합니다."""
        # 리터럴 → 타입명 직접 매핑
        if node.type in self._LITERAL_TYPE_MAP:
            return self._LITERAL_TYPE_MAP[node.type]

        # 식별자 → 변수명 그대로 반환 (EdgeLinker가 타입 해석)
        if node.type == "identifier":
            return source_code[node.start_byte:node.end_byte].decode("utf-8")

        # new Type(...) → 타입명 추출
        if node.type == "object_creation_expression":
            type_node = node.child_by_field_name("type")
            if type_node:
                return source_code[type_node.start_byte:type_node.end_byte].decode("utf-8")

        # (Type) expr → 캐스트 타입명 추출
        if node.type == "cast_expression":
            type_node = node.child_by_field_name("type")
            if type_node:
                return source_code[type_node.start_byte:type_node.end_byte].decode("utf-8")

        # field_access: this.field 등 → 텍스트 그대로
        if node.type == "field_access":
            return source_code[node.start_byte:node.end_byte].decode("utf-8")

        # 그 외 (method_invocation, binary_expression 등) → 해석 불가
        return ""

    # -----------------------------------------------------------------------
    # 파라미터 속성 처리 (METHOD.params)
    # -----------------------------------------------------------------------
    def _extract_params(self, method_node, source_code: bytes) -> tuple[list[ParamInfo], list[str]]:
        """파라미터를 list[ParamInfo]로 추출합니다. qualname 조립용 타입명 리스트도 함께 반환합니다."""
        params_node = method_node.child_by_field_name("parameters")
        if not params_node:
            for child in method_node.children:
                if child.type == "formal_parameters":
                    params_node = child
                    break

        params: list[ParamInfo] = []
        param_types: list[str] = []

        if not params_node:
            return params, param_types

        for child in params_node.children:
            if child.type not in ["formal_parameter", "spread_parameter"]:
                continue

            type_node = child.child_by_field_name("type")
            name_node = child.child_by_field_name("name")

            # 가변인자 처리
            if child.type == "spread_parameter" and (not type_node or not name_node):
                for gc in child.children:
                    if gc.type == "variable_declarator":
                        name_node = gc.child_by_field_name("name")
                    elif gc.type not in ["...", "variable_declarator", "modifiers", "annotation"] and not type_node:
                        type_node = gc

            # 일반 폴백 (인터페이스 메서드 등)
            if not type_node or not name_node:
                for pc in child.children:
                    if pc.type == "identifier" and not name_node:
                        name_node = pc
                    elif pc.type not in ["identifier", "modifiers", "marker_annotation", "annotation",
                                         ",", "...", "line_comment", "block_comment"] and not type_node:
                        type_node = pc

            if type_node and name_node:
                p_type_str = source_code[type_node.start_byte:type_node.end_byte].decode("utf-8")
                p_name = source_code[name_node.start_byte:name_node.end_byte].decode("utf-8")
                # qualname용: 제네릭 제거한 단순 타입명 (예: List<String> → List)
                #   c.f) 오버로딩된 메서드에 대해 유일성이 보장 안되는 것 아닌가? 하는 의문이 들 수 있지만,
                #        Java Compiler(javac) 자체가 List<String> → List 로 저장하기 때문에(Type Erasure), 
                #        컴파일 자체가 안됩니다(안심하라구).
                p_type_simple = self.generic_pattern.sub("", p_type_str)

                # 파라미터 어노테이션 추출 (예: @PathVariable, @RequestBody)
                p_annotation = self._extract_annotations(child, source_code)

                params.append(ParamInfo(
                    name=p_name, 
                    type=self._build_typeinfo(p_type_str), 
                    annotation=p_annotation)
                )
                param_types.append(p_type_simple)

        return params, param_types

    # -----------------------------------------------------------------------
    # 리턴타입 속성 처리 (METHOD.return_type)
    # -----------------------------------------------------------------------
    def _extract_return_type(self, method_node, source_code: bytes) -> TypeInfo | None:
        """메서드의 리턴 타입을 TypeInfo로 추출합니다. 생성자는 None을 반환합니다."""
        if method_node.type == "constructor_declaration":
            return None

        type_node = method_node.child_by_field_name("type")
        if not type_node:
            return None

        type_str = source_code[type_node.start_byte:type_node.end_byte].decode("utf-8")
        if type_str == "void":
            return TypeInfo(given="void", layout=[])

        return self._build_typeinfo(type_str)

    # 메소드 시그니처 추출
    def _extract_signature(self, method_node, source_code: bytes) -> str:
        """메서드의 시그니처(선언부)를 추출합니다. (body 제외)"""
        body_node = method_node.child_by_field_name("body")
        sig_end = body_node.start_byte if body_node else method_node.end_byte
        return source_code[method_node.start_byte:sig_end].decode("utf-8").strip()

    # METHOD.endpoint_uri, METHOD.http_method 처리
    def _extract_endpoint_info(self, method_node, source_code: bytes, base_uri: str) -> tuple[str, str]:
        """메서드의 REST 엔드포인트 정보를 추출합니다. (endpoint_uri, http_method) 튜플 반환."""
        modifiers = method_node.child_by_field_name("modifiers")
        if not modifiers:
            for child in method_node.children:
                if child.type == "modifiers":
                    modifiers = child
                    break
        if not modifiers:
            return "", ""

        # HTTP 메서드 목록
        #   c.f) HEAD, OPTIONS, TRACE 등은 GetMapping 이런게 없고 
        #        @RequestMapping(method = RequestMethod.XXX) 형태로 선언되기 때문에, 
        #        RequestMapping 처리 시 발라냅니다.
        _MAPPING = {
            "GetMapping": "GET", "PostMapping": "POST",
            "PutMapping": "PUT", "DeleteMapping": "DELETE",
            "PatchMapping": "PATCH", "RequestMapping": "ALL",
        }

        # HTTP 메서드 추출
        for child in modifiers.children:
            if child.type in ["annotation", "marker_annotation"]:
                name_node = child.child_by_field_name("name")
                if not name_node:
                    continue
                a_name = source_code[name_node.start_byte:name_node.end_byte].decode("utf-8")
                for key, http_method in _MAPPING.items():
                    if key in a_name:
                        if key == "RequestMapping": # @RequestMapping 추가 처리
                            http_method = self._extract_http_method_kind(child, source_code)
                        # 컨트롤러의 클래스 레벨 URI + 메서드 레벨 URI 조합
                        endpoint_uri = self._combine_uri(base_uri, self._extract_method_uri(child, source_code))

                        return endpoint_uri, http_method

        return "", ""

    # endpoint의 HTTP 메서드 종류 추출 (RequestMapping의 method 속성에서)
    def _extract_http_method_kind(self, annotation_node, source_code: bytes) -> str:
        """@RequestMapping의 method 속성에서 HTTP 메서드를 추출합니다. (예: RequestMethod.GET → "GET")"""
        args = annotation_node.child_by_field_name("arguments")
        if not args:
            return "ALL"

        for child in args.children:
            if child.type == "element_value_pair":
                key = child.child_by_field_name("key")
                value = child.child_by_field_name("value")
                if key and value:
                    key_text = source_code[key.start_byte:key.end_byte].decode("utf-8")
                    if key_text == "method":
                        value_text = source_code[value.start_byte:value.end_byte].decode("utf-8")
                        # {RequestMethod.GET, RequestMethod.POST} 또는 RequestMethod.GET
                        # 중괄호·공백 제거 후 각 항목에서 '.' 뒤 메서드명만 추출
                        raw = value_text.strip("{} ")
                        parts = [p.strip().split(".")[-1] for p in raw.split(",") if p.strip()]
                        return ",".join(parts)
        return "ALL"
    
    # 클래스에 있는 URI 추출
    def _extract_base_uri(self, type_node, source_code: bytes) -> str:
        """클래스 레벨의 @RequestMapping URL을 추출합니다."""
        modifiers = type_node.child_by_field_name("modifiers")
        if not modifiers:
            for child in type_node.children:
                if child.type == "modifiers":
                    modifiers = child
                    break
        if not modifiers:
            return ""

        for child in modifiers.children:
            if child.type in ["annotation", "marker_annotation"]:
                name_node = child.child_by_field_name("name")
                if not name_node:
                    continue
                name_text = source_code[name_node.start_byte:name_node.end_byte].decode("utf-8")
                if "RequestMapping" in name_text:
                    return self._extract_method_uri(child, source_code)
        return ""

    # 메소드에 있는 URI 추출
    def _extract_method_uri(self, annotation_node, source_code: bytes) -> str:
        """어노테이션의 URI 값을 추출합니다. (예: @GetMapping("/api") → "/api")"""
        args = annotation_node.child_by_field_name("arguments")
        if not args:
            return ""

        for child in args.children:
            if child.type == "string_literal":
                return source_code[child.start_byte:child.end_byte].decode("utf-8").strip('"')
            elif child.type == "element_value_pair":
                key = child.child_by_field_name("key")
                value = child.child_by_field_name("value")
                if key and value:
                    key_text = source_code[key.start_byte:key.end_byte].decode("utf-8")
                    if key_text in ("value", "path"):
                        return source_code[value.start_byte:value.end_byte].decode("utf-8").strip('"')
        return ""

    # full URI 조합 (클래스 레벨 + 메서드 레벨)
    def _combine_uri(self, base: str, path: str) -> str:
        """
        기본 URI와 경로를 조합합니다.
        Controller 클래스에 @RequestMapping("/api")가 있고, 메서드에 @GetMapping("/users")가 있으면 → "/api/users"
        다만, 애플리케이션 레벨로 정의된 URI는 잡지 못합니다.
        """
        base = (base or "").rstrip("/")
        path = (path or "").lstrip("/")
        if not base and not path:
            return ""
        return f"{base}/{path}"

    # -----------------------------------------------------------------------
    # Enum 상수 처리
    # -----------------------------------------------------------------------
    def _extract_enum_constants(self, class_body_node, source_code: bytes) -> list[ConstantInfo]:
        """
        Enum 상수를 ConstantInfo 리스트로 추출합니다.
        예) SUCCESS("S2000", "성공") → [ConstantInfo(name="SUCCESS", value="S2000")]
        """
        constants: list[ConstantInfo] = []
        for child in class_body_node.children:
            if child.type == "enum_constant":
                name_node = child.child_by_field_name("name")
                if not name_node:
                    continue
                const_name = source_code[name_node.start_byte:name_node.end_byte].decode("utf-8")

                const_value = const_name
                args_node = child.child_by_field_name("arguments")
                if args_node:
                    for arg in args_node.children:
                        if arg.type == "string_literal":
                            const_value = source_code[arg.start_byte:arg.end_byte].decode("utf-8").strip('"')
                            break
                constants.append(ConstantInfo(name=const_name, value=const_value))

        return constants

    # -----------------------------------------------------------------------
    # TypeInfo 생성 관련
    # -----------------------------------------------------------------------
    def _build_typeinfo(self, type_str: str) -> TypeInfo:
        """TypeInfo 딕셔너리를 생성합니다."""
        if not type_str:
            return TypeInfo(given="", layout=[])
        layout = self._extract_typeinfo_layout(type_str)
        return TypeInfo(given=type_str, layout=layout)

    # TypeInfo.layout 처리
    def _extract_typeinfo_layout(self, type_str: str) -> list[str]:
        """
        타입 문자열에서 모든 개별 타입명을 추출합니다.
        예: "Map<String, List<UserDto>>" → ["Map", "String", "List", "UserDto"]
        예: "UserDto[]" → ["UserDto"]
        """
        if not type_str:
            return []

        parts = self.type_split_pattern.split(type_str)

        # 유효한 타입명만 남기기(불필요한 공백과 제네릭 구문 제거)
        cleaned_types = []
        for p in parts:
            p = p.strip().replace("[]", "").replace("...", "")
            if p:
                cleaned_types.append(p)

        # layout에 넣지 않을 서 기본형·표준 타입은 제외합니다. 
        # 예: int[][] → "int"는 layout에서 제외, "UserDto[]" → "UserDto"는 포함
        # 이는 HAS_PARAMETER / RETURNS 엣지 생성 시, 기본형·표준 타입은 제외하고 사용자 정의 타입에 대해서만 엣지를 생성하기 위함입니다.
        ignored_types = {"?", "extends", "super", "var", "void",
                   "int", "long", "boolean", "byte", "short", "char", "float", "double"}

        # 중복 제거하면서 순서 유지하여 최종 layout 리스트 생성
        seen = set()
        result = []
        for t in cleaned_types:
            simple_name = t.split(".")[-1]
            if simple_name and simple_name not in ignored_types and simple_name not in seen:
                seen.add(simple_name)
                result.append(simple_name)
        return result

    def _is_primitive_type(self, type_name: str) -> bool:
        """기본형·표준 타입 여부를 판단합니다.(나중에 HAS_PARAMETER / RETURNS 엣지 생성 시 활용)"""
        base_type = self.generic_pattern.sub("", type_name).replace("[]", "").strip()
        return base_type in _PRIMITIVE_TYPES
