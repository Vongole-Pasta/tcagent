"""
파싱 결과를 담는 언어 독립적 데이터 구조.
DB 의존성 없음 — 파서와 라이터 사이의 중간 표현(Intermediate Representation).
각 언어 파서는 이 모델들을 생성하고, EdgeLinker/GraphWriter가 이를 소비합니다.

프로퍼티 JSON 타입(TypeInfo, ParamInfo 등)은 graph_db/schema.py에 정의되어 있습니다.
"""
from dataclasses import dataclass, field
from typing import Optional, TypedDict

from graph_db.schema import TypeInfo, ParamInfo, ConstantInfo


@dataclass
class ParsedType:
    """TYPE 노드로 변환될 파싱 결과."""
    qualname: str                   # 완전 한정 이름 (예: com.example.service.UserService)
    name: str                       # 단순 이름 (예: UserService)
    kind: str                       # CLASS | INTERFACE | ENUM | RECORD
    file_path: str                  # 소속 파일 경로
    constants: list[ConstantInfo]   # ENUM 전용: ConstantInfo JSON 문자열
    supertypes: list[str] = field(default_factory=list)  # 상위 타입 이름 목록 (파서: 단순 이름 → EdgeLinker: qualname으로 해석)


@dataclass
class ParsedField:
    """FIELD 노드로 변환될 파싱 결과."""
    qualname: str           # 고유 식별자 (예: com.example.model.User.email)
    type_qualname: str      # 부모 TYPE의 qualname
    name: str               # 필드명
    field_type: TypeInfo    # TypeInfo JSON 문자열: {"given": ..., "layout": [...]}
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
    caller_qualname: str            # 호출자 METHOD의 qualname (com.example.MemberController.login(String))
    target_method_name: str         # 호출 대상 메서드 이름 (getUser)
    object_name: str                # 호출 대상 객체/클래스 이름 (userRepo)
    arg_count: int = -1             # 호출 시 전달된 인자 개수 (-1 = 알 수 없음)
    receiver_method: str = ""       # 체이닝 시 수신 객체를 반환한 메서드명
    receiver_object: str = ""       # 체이닝 시 원래 수신 객체명
    callee_qualname: str = ""       # EdgeLinker가 해석한 호출 대상의 qualname (해석 전에는 빈 문자열)


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
    package_name: str = ""                                      # 패키지/네임스페이스명 (예: "com.example.service")
    imports: list[str] = field(default_factory=list)             # 정규 import (예: ["com.example.model.User"])
    wildcard_imports: list[str] = field(default_factory=list)    # 와일드카드 import의 패키지명 (예: ["com.example.dto"])


@dataclass
class ResolvedEdges:
    """EdgeLinker가 해석한 엣지 배치. GraphWriter가 DB에 기록합니다."""
    params: list[dict] = field(default_factory=list)            # HAS_PARAMETER 배치
    returns: list[dict] = field(default_factory=list)           # RETURNS 배치
    internal_calls: list[dict] = field(default_factory=list)    # 내부 CALLS 배치
    external_calls: list[dict] = field(default_factory=list)    # 외부 CALLS 배치


@dataclass
class ParsedRegistry:
    """
    파싱 결과 인메모리 저장소. 요청별로 따로 인스턴스화하여 싱글턴인 Analyzer이 메모리를 공유하는 것을 회피.

    파일별 파싱 결과(ParsedFileResult)를 축적하고,
    EdgeLinker와 GraphWriter가 이를 참조합니다.
    """

    class FileContext(TypedDict):
        """파일 레벨 컨텍스트. EdgeLinker가 타입 해석 시 참조합니다."""
        package: str                    # 패키지/네임스페이스명 (예: "com.example.service")
        imports: list[str]              # 정규 import 목록 (예: ["com.example.model.User"])
        wildcard_imports: list[str]     # 와일드카드 import의 패키지명 (예: ["com.example.dto"])

    # 노드 저장소
    types: dict[str, ParsedType] = field(default_factory=dict)         # qualname → ParsedType
    fields: dict[str, ParsedField] = field(default_factory=dict)       # qualname → ParsedField
    methods: dict[str, ParsedMethod] = field(default_factory=dict)     # qualname → ParsedMethod

    # 엣지 저장소 (원시 — EdgeLinker가 해석)
    calls: list[ParsedCallEdge] = field(default_factory=list)
    param_edges: list[ParsedParameterEdge] = field(default_factory=list)
    return_edges: list[ParsedReturnEdge] = field(default_factory=list)

    # 파일 레벨 컨텍스트 (EdgeLinker의 타입 해석용)
    file_contexts: dict[str, 'ParsedRegistry.FileContext'] = field(default_factory=dict)  # file_path → FileContext

    # EdgeLinker가 해석한 엣지 배치 (resolve() 후 세팅)
    resolved: ResolvedEdges = field(default_factory=ResolvedEdges)

    def collect(self, result: ParsedFileResult):
        """
        한 파일의 파싱 결과(ParsedFileResult)를 등록소에 축적합니다.

        ParsedFileResult는 파서가 생성한 일회성 전달 컨테이너이며,
        이 메서드에서 노드·엣지·컨텍스트를 각각의 저장소에 분배합니다.

        분배 구조:
          - 노드 (qualname 키로 중복 방지)  → types, fields, methods
          - 엣지 (순서 유지, 중복 허용)      → calls, param_edges, return_edges
          - 컨텍스트 (file_path 키)          → file_contexts
        """
        # ── 노드 등록 (qualname 기준 upsert) ──
        for t in result.types:
            self.types[t.qualname] = t
        for f in result.fields:
            self.fields[f.qualname] = f
        for m in result.methods:
            self.methods[m.qualname] = m

        # ── 원시 엣지 축적 (EdgeLinker가 해석) ──
        self.calls.extend(result.calls)
        self.param_edges.extend(result.parameter_edges)
        self.return_edges.extend(result.return_edges)

        # ── 파일 레벨 컨텍스트 저장 ──
        # EdgeLinker가 동명 타입을 import/패키지 기준으로 구분할 때 참조합니다.
        # types[0].file_path를 키로 사용: 한 파일의 모든 타입은 동일 file_path를 공유하므로.
        if result.types:
            file_path = result.types[0].file_path
            self.file_contexts[file_path] = {
                "package": result.package_name,
                "imports": result.imports,
                "wildcard_imports": result.wildcard_imports,
            }
