class HappyCaseQueries:
    """Happy Case 시나리오 생성을 위한 Graph DB Cypher 쿼리 모음"""

    # 메서드의 파라미터/반환 타입 및 중첩 DTO(최대 5레벨)의 필드 구조 조회
    # 1. METHOD -> (HAS_PARAMETER|RETURNS) -> TYPE (직접 관계)
    # 2. METHOD -> (CONTAINS) -> PARAMETER -> (OF_TYPE) -> TYPE (실제 스캔 구조)
    # 파라미터(Request) DTO 구조 조회
    RETRIEVER_NODE_GET_REQUEST_DTO_STRUCTURE = """
    MATCH (m:METHOD {qualname: $qualname})
    OPTIONAL MATCH (m)-[:HAS_PARAMETER]->(root1:TYPE)
    OPTIONAL MATCH (m)-[:CONTAINS]->(:PARAMETER)-[:OF_TYPE]->(root2:TYPE)
    WITH DISTINCT root1, root2
    UNWIND [root1, root2] as root
    WITH DISTINCT root WHERE root IS NOT NULL
    OPTIONAL MATCH path = (root)-[:CONTAINS|OF_TYPE *0..10]->(t:TYPE)
    WITH DISTINCT t
    WHERE t IS NOT NULL
    MATCH (t)-[:CONTAINS]->(f:FIELD)
    RETURN t.name as type_name, f.name as field_name, f.type as field_type
    """

    # 반환(Response) DTO 구조 조회
    RETRIEVER_NODE_GET_RESPONSE_DTO_STRUCTURE = """
    MATCH (m:METHOD {qualname: $qualname})
    OPTIONAL MATCH (m)-[:RETURNS]->(root:TYPE)
    WITH DISTINCT root WHERE root IS NOT NULL
    OPTIONAL MATCH path = (root)-[:CONTAINS|OF_TYPE *0..10]->(t:TYPE)
    WITH DISTINCT t
    WHERE t IS NOT NULL
    MATCH (t)-[:CONTAINS]->(f:FIELD)
    RETURN t.name as type_name, f.name as field_name, f.type as field_type
    """
