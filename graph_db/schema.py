"""
Graph Database Schema Definition
Auto-generated from GrahpRag Database Inspection
"""

NODE_SCHEMA = {
    # [FILE] (파일 노드)
    # - 식별자(Identifier): path (프로젝트 내 상대 경로)
    # - 'path'와 'package'를 구분하는 이유:
    #   1. 동명이인 파일 구분: src/main/java/User.java vs src/test/java/User.java (패키지명은 같음)
    #   2. 자바 외 파일: application.yml 등은 패키지가 없음
    #   3. Default Package: 패키지 선언이 없는 파일도 물리적 위치는 필요함
    #   따라서 'path'는 물리적 파일 식별용(UI, I/O), 'package'는 논리적 코드 연결용으로 사용합니다.
    "FILE": [
        "hash",      # 파일 내용의 SHA-256 해시값 (변경 감지용)
        "language",  # 언어 (예: "java", "python")
        "name",      # 파일명 (예: UserService.java)
        "package",   # 자바 패키지명 (예: com.example.service)
        "path",      # 고유 식별자: 상대 경로 (예: src/main/java/com/example/service/UserService.java)
        "project"    # 프로젝트 식별자 (예: "default")
    ],
    
    # [TYPE] (타입 노드)
    # - 식별자(Identifier): fullName (패키지명 + 클래스명)
    # - Class, Interface, Enum, Record 등 자바 타입을 통칭
    "TYPE": [
        "fullName",  # 고유 식별자: com.example.service.UserService
        "name",      # 단순 클래스명: UserService
        "type"       # 타입 종류: [CLASS, INTERFACE, ENUM]
    ],
    
    # [METHOD] (메서드 노드)
    # - 식별자(Identifier): signature (전체 서명)
    "METHOD": [
        "endpoint",    # API 엔드포인트 URL (Controller인 경우)
        "hash",        # 메서드 바디 해시값 (변경 감지용)
        "http_method", # HTTP 메서드: [GET, POST, PUT, DELETE, PATCH, '']
        "last_scan_id", # 마지막 분석 스캔 ID
        "name",        # 메서드 이름
        "signature",   # 고유 식별자: com.example.ClassName.methodName(ParamType)
        "source",      # 소스 코드 본문
        "status"       # 상태 변경: [NEW, MODIFIED, AS-IS, DELETED]
    ],
    
    # [ExternalCall] (외부 호출 노드)
    # - 식별자(Identifier): name (단순 메서드명)
    # - 프로젝트 내에 소스 코드가 없는 라이브러리나 외부 API 호출을 나타냄
    # - 상세 분석 대상이 아니므로 이름만 저장하여 호출 흐름의 끝점으로 사용
    "ExternalCall": [
        "name"         # 호출된 메서드 이름 (예: println, save)
    ],
    
    # [PARAMETER] (파라미터 노드)
    # - 식별자(Identifier): 별도 고유 ID 없음 (METHOD에 종속적)
    # - 메서드의 입력 인자를 나타내며, 순서(index)와 타입 정보를 가짐
    "PARAMETER": [
        "name",        # 파라미터 변수명 (예: userId)
        "type",        # 파라미터 타입 (예: Long)
        "index"        # 인자 순서 (0부터 시작)
    ],
    
    # [FIELD] (필드 노드)
    # - 식별자(Identifier): 별도 고유 ID 없음 (TYPE에 종속적)
    # - 클래스/객체의 멤버 변수, Enum 상수, Record 컴포넌트를 나타냄
    "FIELD": [
        "name",        # 필드명 (예: email, ACTIVE)
        "type"         # 필드 타입 (예: String, Status)
    ]
}

RELATIONSHIP_SCHEMA = [
    # Format: StartLabel -> RelationshipType -> EndLabel
    "FILE -> CONTAINS -> TYPE",
    "TYPE -> CONTAINS -> METHOD",
    "METHOD -> CALLS -> ExternalCall",
    "METHOD -> CALLS -> METHOD",
    # Structure
    "METHOD -> CONTAINS -> PARAMETER",
    "TYPE -> CONTAINS -> FIELD",
    # Type Reference
    "PARAMETER -> OF_TYPE -> TYPE",
    "FIELD -> OF_TYPE -> TYPE"
]

class NodeLabel:
    """Dynamic Enum-like access for Node Labels"""
    FILE = "FILE"
    TYPE = "TYPE"
    METHOD = "METHOD"
    EXTERNAL_CALL = "ExternalCall"
    PARAMETER = "PARAMETER"
    FIELD = "FIELD"

class EdgeType:
    """Dynamic Enum-like access for Edge Types"""
    CONTAINS = "CONTAINS"
    CALLS = "CALLS"
    OF_TYPE = "OF_TYPE"
