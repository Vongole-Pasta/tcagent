"""
파싱 결과를 담는 언어 독립적 데이터 구조.
DB 의존성 없음 — 파서와 라이터 사이의 중간 표현(Intermediate Representation).
각 언어 파서는 이 모델들을 생성하고, GraphWriter가 이를 소비합니다.

프로퍼티 JSON 타입(TypeInfo, ParamInfo 등)은 graph_db/schema.py에 정의되어 있습니다.
"""
from dataclasses import dataclass, field
from typing import Optional

from graph_db.schema import TypeInfo, ParamInfo, ConstantInfo


@dataclass
class ParsedType:
    """TYPE 노드로 변환될 파싱 결과."""
    qualname: str                   # 완전 한정 이름 (예: com.example.service.UserService)
    name: str                       # 단순 이름 (예: UserService)
    kind: str                       # CLASS | INTERFACE | ENUM | RECORD
    file_path: str                  # 소속 파일 경로
    constants: list[ConstantInfo]   # ENUM 전용: ConstantInfo JSON 문자열


@dataclass
class ParsedField:
    """FIELD 노드로 변환될 파싱 결과."""
    type_qualname: str      # 부모 TYPE의 qualname
    name: str               # 필드명
    field_type: str         # TypeInfo JSON 문자열: {"given": ..., "layout": [...]}
    constraint: str = ""    # 유효성 제약조건 (예: "@NotBlank")


@dataclass
class ParsedMethod:
    """METHOD 노드로 변환될 파싱 결과."""
    qualname: str           # 고유 식별자 (예: com.example.UserService.getUserById(String))
    name: str               # 메서드 이름
    source: str             # 소스 코드 전문
    class_qualname: str     # 소속 클래스의 qualname
    signature: str          # 전체 선언문 (표시용)
    params: list[ParamInfo]         # 파라미터 목록
    return_type: Optional[TypeInfo]  # 리턴 타입 정보
    method_hash: str        # 소스 해시 (변경 감지용)
    scan_id: Optional[str] = None
    endpoint_uri: str = ""  # REST 엔드포인트 URL
    http_method: str = ""   # HTTP 메서드


@dataclass
class ParsedCallEdge:
    """CALLS 엣지로 변환될 파싱 결과."""
    caller_qualname: str    # 호출자 METHOD의 qualname
    target_method_name: str # 호출 대상 메서드 이름
    object_name: str        # 호출 대상 객체/클래스 이름
    count: int              # 호출 횟수


@dataclass
class ParsedParameterEdge:
    """HAS_PARAMETER 엣지로 변환될 파싱 결과."""
    method_qualname: str    # METHOD의 qualname
    param_info: ParamInfo   # 파라미터 정보


@dataclass
class ParsedReturnEdge:
    """RETURNS 엣지로 변환될 파싱 결과."""
    method_qualname: str    # METHOD의 qualname
    return_info: TypeInfo   # 리턴 타입 정보


@dataclass
class ParsedFileResult:
    """한 소스 파일의 전체 파싱 결과."""
    types: list[ParsedType] = field(default_factory=list)
    methods: list[ParsedMethod] = field(default_factory=list)
    fields: list[ParsedField] = field(default_factory=list)
    calls: list[ParsedCallEdge] = field(default_factory=list)
    parameter_edges: list[ParsedParameterEdge] = field(default_factory=list)
    return_edges: list[ParsedReturnEdge] = field(default_factory=list)
