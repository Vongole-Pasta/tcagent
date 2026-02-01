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
    "NAMESPACE_BLOCK -> CONTAINS -> FILE",
    "FILE -> CONTAINS -> TYPE_DECL",
    "TYPE_DECL -> CONTAINS -> METHOD",
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
    CONTAINS = "CONTAINS"
    CALLS = "CALLS"
