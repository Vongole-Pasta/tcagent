class HappyCaseQueries:
    """Happy Case 시나리오 생성을 위한 Graph DB Cypher 쿼리 모음"""

    # 메서드의 파라미터/반환 타입 및 중첩 DTO의 필드 구조 조회
    # METHOD -> (HAS_PARAMETER|RETURNS) -> TYPE (직접 관계)
    # 파라미터(Request) DTO 구조 조회 — Enum TYPE의 FIELD는 제외
    RETRIEVER_NODE_GET_REQUEST_DTO_STRUCTURE = """
    MATCH (m:METHOD {qualname: $qualname})
    OPTIONAL MATCH (m)-[:HAS_PARAMETER]->(root:TYPE)
    WITH DISTINCT root WHERE root IS NOT NULL
    OPTIONAL MATCH path = (root)-[:CONTAINS*0..10]->(t:TYPE)
    WITH DISTINCT t
    WHERE t IS NOT NULL AND coalesce(t.kind, '') <> 'ENUM'
    MATCH (t)-[:CONTAINS]->(f:FIELD)
    RETURN t.name as type_name, f.name as field_name, f.type as field_type
    """

    # 반환(Response) DTO 구조 조회 — Enum TYPE의 FIELD는 제외
    RETRIEVER_NODE_GET_RESPONSE_DTO_STRUCTURE = """
    MATCH (m:METHOD {qualname: $qualname})
    OPTIONAL MATCH (m)-[:RETURNS]->(root:TYPE)
    WITH DISTINCT root WHERE root IS NOT NULL
    OPTIONAL MATCH path = (root)-[:CONTAINS*0..10]->(t:TYPE)
    WITH DISTINCT t
    WHERE t IS NOT NULL AND coalesce(t.kind, '') <> 'ENUM'
    MATCH (t)-[:CONTAINS]->(f:FIELD)
    RETURN t.name as type_name, f.name as field_name, f.type as field_type
    """

    # Enum TYPE의 constants 조회 (파라미터 측)
    RETRIEVER_NODE_GET_REQUEST_ENUM_CONSTANTS = """
    MATCH (m:METHOD {qualname: $qualname})
    OPTIONAL MATCH (m)-[:HAS_PARAMETER]->(root:TYPE)
    WITH DISTINCT root WHERE root IS NOT NULL
    OPTIONAL MATCH path = (root)-[:CONTAINS*0..10]->(t:TYPE)
    WITH DISTINCT t
    WHERE t IS NOT NULL AND t.kind = 'ENUM' AND t.constants <> ''
    RETURN t.name as type_name, t.constants as constants
    """

    # Enum TYPE의 constants 조회 (반환 측)
    RETRIEVER_NODE_GET_RESPONSE_ENUM_CONSTANTS = """
    MATCH (m:METHOD {qualname: $qualname})
    OPTIONAL MATCH (m)-[:RETURNS]->(root:TYPE)
    WITH DISTINCT root WHERE root IS NOT NULL
    OPTIONAL MATCH path = (root)-[:CONTAINS*0..10]->(t:TYPE)
    WITH DISTINCT t
    WHERE t IS NOT NULL AND t.kind = 'ENUM' AND t.constants <> ''
    RETURN t.name as type_name, t.constants as constants
    """
