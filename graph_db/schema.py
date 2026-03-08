"""
Graph Database Schema Definition
Neo4j 그래프 DB의 노드/관계 스키마와 프로퍼티에 사용되는 JSON 타입을 정의합니다.
"""
from typing import TypedDict


# -----------------------------------------------------------------------
# 프로퍼티 JSON 타입 (TypedDict)
# -----------------------------------------------------------------------

class TypeInfo(TypedDict):
    """제네릭 타입 포함, 타입을 나타내는 정보. DB에 JSON 문자열로 저장됩니다."""
    given: str              # 원본 타입 문자열 (예: "List<User>")
    layout: list[str]       # 개별 타입명 목록 (예: ["List", "User"])


class ParamInfo(TypedDict):
    """파라미터 정보. METHOD.params의 원소로 사용됩니다."""
    name: str               # 파라미터명
    type: TypeInfo           # 타입 정보
    annotation: str         # 어노테이션 (예: "@RequestAttribute", "@NotBlank") 등


class ConstantInfo(TypedDict):
    """Enum 상수 정보. TYPE.constants의 원소로 사용됩니다."""
    name: str               # 상수 이름
    value: str              # 상수 값

NODE_SCHEMA = {
    # [FILE] (파일 노드)
    # - 식별자(Identifier): path (파일 경로)
    "FILE": {
        "path":     str,    # ROOT 기준으로 상대 경로 (ROOT = zip파일 최상위 결로)
        "qualname": str,    # 고유 식별자(qualified name): AST/파서 라이브러리에서 사용하는 용어
        "name":     str,    # 파일명 (예: UserService.java)
        "language": str,    # 언어 (예: "java", "python")
        "project":  str,    # 프로젝트 식별자 (예: "default")
        "hash":     str,    # 파일 내용의 SHA-256 해시값 (변경 감지용)
    },
    
    # [TYPE] (타입 노드): Class, Interface, Enum, Record 등 자바 타입을 통칭
    # - 식별자(Identifier): qualname (패키지명 + 클래스명)
    "TYPE": {
        "qualname":     str,                # 고유 식별자: com.example.service.UserService
        "name":         str,                # 단순이름: UserService
        "kind":         str,                # 타입 종류: [CLASS, INTERFACE, ENUM, RECORD 등]
        "constants":    list[ConstantInfo], # 상수값 리스트 (JSON 배열) (ENUM인 경우)
        "supertypes":   list[str],          # 상위 타입 단순 이름 목록 (extends + implements 통합)
    },
    
    # [FIELD] (필드 노드): 클래스/객체의 멤버 변수, Enum 상수,
    # - 식별자(Identifier): 없음 (TYPE에 종속적)
    "FIELD": {
        "qualname":   str,      # 고유 식별자: com.example.model.User.email
        "name": str,            # 필드명 (예: email, ACTIVE)
        "type": TypeInfo,       # 필드 타입 (JSON)
        "constraint": str       # 유효성 제약조건 (예: "@NotBlank", "@Pattern" 등)
    },

    # [METHOD] (메서드 노드)
    # - 식별자(Identifier): qualname
    "METHOD": {
        "qualname":     str,            # 고유 식별자: com.example.service.UserService.getUserById(String)
        "hash":         str,            # 메서드 바디 해시값 (변경 감지용)
        "signature":    str,            # 함수 시그니처 (예: public ResponseEntity<UserDto> getUserById(String id))
        "name":         str,            # 메서드 이름
        "params":       list[ParamInfo],# 파라미터 정보(JSON 배열)
        "return_type":  TypeInfo,       # 리턴타입 정보(JSON)
        "endpoint_uri": str,            # API 엔드포인트 URL (Controller인 경우)
        "http_method":  str,            # HTTP 메서드: [GET, POST, PUT, DELETE, PATCH, '']
        "source":       str,            # 함수 스코프 소스 코드 본문
        "last_scan_id": str,            # 마지막 분석 스캔 ID
        "status":       str             # 상태 변경: [NEW, MODIFIED, AS-IS, DELETED]
    },
    
    # [EXTERNAL_CALL] (외부 호출 노드)
    # - 식별자(Identifier): name (단순 메서드명)
    # - 프로젝트 내에 소스 코드가 없는 라이브러리나 외부 API 호출을 나타냄
    # - 상세 분석 대상은 아니지만 이 정보를 써서 LLM이 호출된 메서드의 역할을 유추할 수 있도록 signature와 fqualname도 저장합니다.
    "EXTERNAL_CALL": {
        "qualname":     str,     # 호출된 메서드의 완전한 이름 (예: java.io.PrintStream.println)
        "name":         str,         # 호출된 메서드 이름 (예: println, save)
        "signature":    str    # 호출된 메서드의 전체 서명 
    }

}

RELATIONSHIP_SCHEMA = [
    # Format: StartLabel -> RelationshipType -> EndLabel
    "FILE -> CONTAINS -> TYPE",
    "TYPE -> CONTAINS -> METHOD",
    "TYPE -> CONTAINS -> FIELD",
    "FIELD -> CONTAINS -> TYPE",
    "METHOD -> CALLS -> METHOD",
    "METHOD -> CALLS -> EXTERNAL_CALL",
    "METHOD -> HAS_PARAMETER -> TYPE",
    "METHOD -> RETURNS -> TYPE",
]

class NodeLabel:
    """Dynamic Enum-like access for Node Labels"""
    FILE = "FILE"
    TYPE = "TYPE"
    METHOD = "METHOD"
    EXTERNAL_CALL = "EXTERNAL_CALL"
    FIELD = "FIELD"


class EdgeType:
    """Dynamic Enum-like access for Edge Types"""
    CONTAINS = "CONTAINS"
    CALLS = "CALLS"
    HAS_PARAMETER = "HAS_PARAMETER"
    RETURNS = "RETURNS"

