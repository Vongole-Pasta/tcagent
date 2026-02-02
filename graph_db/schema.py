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
        "package"
    ],
    "TYPE": [
        "fullName",
        "name",
        "type"     
    ],
    "METHOD": [
        "args",
        "endpoint",
        "hash",
        "http_method",
        "last_scan_id",
        "name",
        "signature",
        "source",
        "status"
    ],
    "ExternalCall": [
        "name"
    ]
}

RELATIONSHIP_SCHEMA = [
    # Format: StartLabel -> RelationshipType -> EndLabel
    "FILE -> CONTAINS -> TYPE",
    "TYPE -> CONTAINS -> METHOD",
    "METHOD -> CALLS -> ExternalCall",
    "METHOD -> CALLS -> METHOD"
]

class NodeLabel:
    """Dynamic Enum-like access for Node Labels"""
    FILE = "FILE"
    TYPE = "TYPE"
    METHOD = "METHOD"
    EXTERNAL_CALL = "ExternalCall"

class EdgeType:
    """Dynamic Enum-like access for Edge Types"""
    CONTAINS = "CONTAINS"
    CALLS = "CALLS"
