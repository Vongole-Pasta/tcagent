from enum import Enum

class NodeLabel(Enum):
    """
    그래프 DB에서 사용하는 노드 라벨(Label) 상수를 정의합니다.
    (예: FILE, METHOD, CLASS 등)
    """
    FILE = "FILE"
    METHOD = "METHOD"
    CLASS = "CLASS"
    INTERFACE = "INTERFACE"
    PACKAGE = "PACKAGE"  # For Java
    MODULE = "MODULE"    # For Python (if needed)
    
    # Internal structure
    CONTROL_STRUCTURE = "CONTROL_STRUCTURE"
    CALL = "CALL"
    PARAMETER = "PARAMETER"
    RETURN = "RETURN"
    ANNOTATION = "ANNOTATION"
    LITERAL = "LITERAL"
    
    # External
    EXTERNAL_CALL = "ExternalCall"
    
    # Unified Types for Architecture
    TYPE_DECL = "TYPE_DECL"
    MEMBER = "MEMBER"
    NAMESPACE_BLOCK = "NAMESPACE_BLOCK"

class EdgeType(Enum):
    """
    그래프 DB에서 사용하는 엣지 타입(Relationship Type) 상수를 정의합니다.
    (예: CALLS, CONTAINS, AST 등)
    """
    AST = "AST"
    CALLS = "CALLS"
    CONTAINS = "CONTAINS"
    INHERITS = "INHERITS"
    IMPORTS = "IMPORTS"
    
    # Detailed Flow
    HAS_PARAM = "HAS_PARAM"
    HAS_EXIT = "HAS_EXIT"
    ANNOTATED_BY = "ANNOTATED_BY"
