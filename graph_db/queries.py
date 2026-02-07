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
    MATCH (m:METHOD)<-[:CONTAINS]-(c:TYPE)
    WHERE elementId(m) = $method_id OR m.id = $method_id
    RETURN c.name as class_name, c.source as class_source
    """

    GET_METHOD_FILE = """
    MATCH (m:METHOD)<-[:CONTAINS]-(c:TYPE)<-[:CONTAINS]-(f:FILE)
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

    # --- New Frontend Support Queries ---

    GET_ALL_METHODS = """
    MATCH (m:METHOD)
    RETURN elementId(m) as id, m.name as name, m.signature as signature, m.endpoint as endpoint, m.http_method as http_method, m.status as status
    ORDER BY m.name
    """
    
    GET_ALL_ENDPOINTS = """
    MATCH (m:METHOD)
    WHERE m.endpoint IS NOT NULL
    OPTIONAL MATCH (m)-[:CALLS*0..]->(d:METHOD)
    WITH m, collect(DISTINCT d.status) as statuses
    RETURN elementId(m) as id, m.name as name, m.endpoint as endpoint, m.http_method as http_method, statuses
    ORDER BY m.endpoint
    """

    GET_UPSTREAM_IMPACT = """
    MATCH path = (source:METHOD)-[:CALLS*0..]->(target:METHOD)
    WHERE (elementId(target) = $method_id OR target.id = $method_id)
    RETURN path
    LIMIT 100
    """

    GET_DOWNSTREAM_FLOW = """
    MATCH path = (source:METHOD)-[:CALLS*0..]->(target:METHOD)
    WHERE (elementId(source) = $method_id OR source.id = $method_id)
    RETURN path
    LIMIT 100
    """
    
    # --- Change Detection Helpers ---
    
    GET_FILE_HASH = """
    MATCH (f:FILE {path: $file_path})
    RETURN f.hash as hash
    """

    # --- Status Management Queries ---
    
    DELETE_PROJECT_DELETED_NODES = """
    MATCH (f:FILE {project: $project})
    
    // 1. Delete DELETED descendants (Methods, Types)
    WITH f
    OPTIONAL MATCH (f)-[:CONTAINS*]->(n)
    WHERE n.status = 'DELETED' AND NOT n:FILE
    DETACH DELETE n
    
    // 2. Delete DELETED Files
    WITH f
    WHERE f.status = 'DELETED'
    DETACH DELETE f
    """
    
    GET_PROJECT_FILES_HASH = """
    MATCH (f:FILE)
    WHERE f.project = $project
    RETURN f.path as path, f.hash as hash
    """
    
    MARK_FILE_DELETED_AND_ISOLATE = """
    MATCH (f:FILE {path: $path, project: $project})
    SET f.status = 'DELETED'
    WITH f
    # Mark all children (Classes, Methods) as DELETED
    MATCH (f)-[:CONTAINS*0..]->(node)
    SET node.status = 'DELETED'
    WITH node
    # Remove only CALLS relationships to isolate from flow
    OPTIONAL MATCH (node)-[r:CALLS]-()
    DELETE r
    """
