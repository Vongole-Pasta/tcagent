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
        "package", # Added
        "type"     # Added
        # "source" Removed
        # "lineNumber" Removed
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
    "CLASS": [
        "fullName",
        "name",
        "package",
        "type"
    ],
    "PACKAGE": [
        "fullName",
        "name"
    ],
    "ExternalCall": [
        "name"
    ]
}

RELATIONSHIP_SCHEMA = [
    # Format: StartLabel -> RelationshipType -> EndLabel
    "CLASS -> BELONGS_TO -> PACKAGE",
    "CLASS -> CONTAINS -> METHOD",
    "FILE -> AST -> METHOD",
    "FILE -> AST -> NAMESPACE_BLOCK",
    "FILE -> AST -> TYPE_DECL",
    "FILE -> CONTAINS -> METHOD",
    "FILE -> DEFINES -> CLASS",
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
    CLASS = "CLASS"
    PACKAGE = "PACKAGE"
    EXTERNAL_CALL = "ExternalCall"

class EdgeType:
    """Dynamic Enum-like access for Edge Types"""
    BELONGS_TO = "BELONGS_TO"
    CONTAINS = "CONTAINS"
    AST = "AST"
    DEFINES = "DEFINES"
    CALLS = "CALLS"
