"""
Graph Database Schema Definition
Auto-generated from GrahpRag Database Inspection
"""

NODE_SCHEMA = {
    "FILE": [
        "hash",
        "language",
        "name",
        "path",
        "project",
        "status"
    ],
    "TYPE_DECL": [
        "fullName",
        "name",
        "package",
        "type"     
    ],
    "METHOD": [
        "args",
        "endpoint",
        "hash",
        "http_method",
        "last_scan_id",
        "lineNumber",
        "name",
        "signature",
        "source",
        "status"
    ],
    "NAMESPACE_BLOCK": [
        "fullName",
        "name"
    ],
    "ExternalCall": [
        "name"
    ]
}

RELATIONSHIP_SCHEMA = [
    # Format: StartLabel -> RelationshipType -> EndLabel
    "TYPE_DECL -> BELONGS_TO -> NAMESPACE_BLOCK",
    "TYPE_DECL -> CONTAINS -> METHOD",
    "FILE -> AST -> METHOD",
    "FILE -> AST -> NAMESPACE_BLOCK",
    "FILE -> AST -> TYPE_DECL",
    "FILE -> CONTAINS -> METHOD",
    "FILE -> DEFINES -> TYPE_DECL",
    "FILE -> DEFINES -> METHOD",
    "METHOD -> CALLS -> ExternalCall",
    "METHOD -> CALLS -> METHOD"
]

class NodeLabel:
    """Dynamic Enum-like access for Node Labels"""
    FILE = "FILE"
    TYPE_DECL = "TYPE_DECL"
    METHOD = "METHOD"
    NAMESPACE_BLOCK = "NAMESPACE_BLOCK"
    EXTERNAL_CALL = "ExternalCall"

class EdgeType:
    """Dynamic Enum-like access for Edge Types"""
    BELONGS_TO = "BELONGS_TO"
    CONTAINS = "CONTAINS"
    AST = "AST"
    DEFINES = "DEFINES"
    CALLS = "CALLS"
