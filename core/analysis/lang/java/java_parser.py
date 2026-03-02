"""
순수 Java AST 파싱 모듈.
tree-sitter를 사용하여 Java 소스 코드에서 타입, 메서드, 필드, 호출 관계를 추출합니다.
DB 의존성 없음 — 파싱 결과는 persistence/models.py의 dataclass로 반환됩니다.
"""
import logging
import re

from core.analysis.persistence.models import (
    TypeInfo, ConstantInfo, ParsedType, ParsedFileResult,
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

    def __init__(self):
        self.generic_pattern = re.compile(r"<.*>")
        self.type_split_pattern = re.compile(r"[<>, \t]+")

    # -----------------------------------------------------------------------
    # 진입점
    # -----------------------------------------------------------------------
    def parse(self, tree, source_code: bytes, file_path: str, scan_id: str | None = None) -> ParsedFileResult:
        """
        Tree-sitter 파싱 트리를 순회하며 패키지, 클래스, 메서드 정보를 추출합니다.

        Args:
            tree: 파싱된 구문 트리
            source_code: 원본 소스 코드
            file_path: 파일 경로
            scan_id: 이번 분석 세션의 고유 아이디 (삭제된 노드 식별용)

        Returns:
            ParsedFileResult: 파싱 결과 (타입, 메서드, 필드, 호출 등)
        """
        result = ParsedFileResult()
        root_node = tree.root_node

        package_name = self._get_package_name(root_node, source_code)
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

        # ParsedType으로 result.types에 추가
        result.types.append(ParsedType(
            qualname=qualname,
            name=class_name,
            kind=kind,
            file_path=file_path,
            constants=constants,
        ))

        # body 탐색
        body_node = node.child_by_field_name("body")
        if not body_node:
            for child in node.children:
                if child.type in ["class_body", "interface_body", "enum_body"]:
                    body_node = child
                    break

        if body_node:
            # Inner Class 재귀 호출
            self._traverse_types(body_node, source_code, file_path, package_name,
                                 result, qualname, scan_id)

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
