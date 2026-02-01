class CypherQueries:
    """
    시스템에서 사용하는 주요 Cypher 쿼리문들을 중앙 관리하는 클래스입니다.
    문맥 검색, 호출 추적, 변경 감지 등의 쿼리가 포함되어 있습니다.
    """
    # --- Context Fetching Queries ---
    
    GET_METHOD_CONTEXT = """
    MATCH (m:METHOD) WHERE elementId(m) = $method_id OR m.id = $method_id
    RETURN m.name as name, m.signature as signature, m.source as source
    """
    
    GET_CALLERS = """
    MATCH (m:METHOD)<-[:CALLS*1..2]-(caller)
    WHERE elementId(m) = $method_id OR m.id = $method_id
    RETURN DISTINCT elementId(caller) as id, caller.name as name, caller.source as source
    LIMIT $limit
    """
    
    GET_CALLEES = """
    MATCH (m:METHOD)-[:CALLS*1..2]->(callee)
    WHERE elementId(m) = $method_id OR m.id = $method_id
    RETURN DISTINCT elementId(callee) as id, callee.name as name, callee.source as source
    LIMIT $limit
    """
    
    GET_CLASS_CONTEXT = """
    MATCH (m:METHOD)<-[:CONTAINS]-(c:TYPE_DECL)
    WHERE elementId(m) = $method_id OR m.id = $method_id
    RETURN c.name as class_name, c.source as class_source
    """

    GET_METHOD_FILE = """
    MATCH (m:METHOD)<-[:CONTAINS]-(c:TYPE_DECL)<-[:CONTAINS]-(f:FILE)
    WHERE elementId(m) = $method_id OR m.id = $method_id
    RETURN f.path as file_path, f.name as file_name
    """
    
    # --- Impact Analysis Queries ---
    
    IMPACT_ANALYSIS_DOWNSTREAM = """
    MATCH (changed:METHOD)<-[:CALLS*1..3]-(impacted)
    WHERE elementId(changed) = $method_id OR changed.id = $method_id
    RETURN DISTINCT elementId(impacted) as id, impacted.name as name, length(path) as distance
    ORDER BY distance ASC
    LIMIT $limit
    """
    
    # --- Change Detection Helpers ---
    
    GET_FILE_HASH = """
    MATCH (f:FILE {path: $file_path})
    RETURN f.hash as hash
    """
