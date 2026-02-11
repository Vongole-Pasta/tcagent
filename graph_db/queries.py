class CypherQueries:
    """
    시스템에서 사용하는 주요 Cypher 쿼리문들을 중앙 관리하는 클래스입니다.
    문맥 검색, 호출 추적, 변경 감지 등의 쿼리가 포함되어 있습니다.
    """
    # --- Context Fetching Queries ---
    
    
    # [메서드 상세 조회]
    # 특정 메서드 ID를 입력받아 이름, 시그니처, 소스 코드를 반환합니다.
    # Frontend: 상세 패널(DetailPanel)에서 소스 코드 보기용
    GET_METHOD_CONTEXT = """
    MATCH (m:METHOD) WHERE elementId(m) = $method_id OR m.id = $method_id
    RETURN m.name as name, m.signature as signature, m.source as source
    """
    

    
    # [클래스 문맥 조회]
    # 특정 메서드가 속한 클래스(TYPE)의 정보를 조회합니다.
    GET_CLASS_CONTEXT = """
    MATCH (m:METHOD)<-[:CONTAINS]-(c:TYPE)
    WHERE elementId(m) = $method_id OR m.id = $method_id
    RETURN c.name as class_name, c.source as class_source
    """

    # [파일 경로 조회]
    # 특정 메서드가 속한 파일의 경로와 이름을 조회합니다.
    GET_METHOD_FILE = """
    MATCH (m:METHOD)<-[:CONTAINS]-(c:TYPE)<-[:CONTAINS]-(f:FILE)
    WHERE elementId(m) = $method_id OR m.id = $method_id
    RETURN f.path as file_path, f.name as file_name
    """
    
    # --- Impact Analysis Queries ---
    


    # --- New Frontend Support Queries ---

    # [모든 메서드 목록 조회]
    # 프로젝트 내의 모든 메서드를 조회하여 검색 기능을 지원합니다.
    GET_ALL_METHODS = """
    MATCH (m:METHOD)
    RETURN elementId(m) as id, m.name as name, m.signature as signature, m.endpoint as endpoint, m.http_method as http_method, m.status as status
    ORDER BY m.name
    """
    
    # [API 엔드포인트 목록 조회]
    # API 엔드포인트(URL) 정보를 가진 메서드만 필터링하여 조회합니다.
    # 각 엔드포인트가 호출하는 하위 메서드들의 상태(NEW/MODIFIED 등)를 집계하여 보여줍니다.
    GET_ALL_ENDPOINTS = """
    MATCH (m:METHOD)
    WHERE m.endpoint IS NOT NULL
    OPTIONAL MATCH (m)-[:CALLS*0..]->(d:METHOD)
    WITH m, collect(DISTINCT d.status) as statuses
    RETURN elementId(m) as id, m.name as name, m.endpoint as endpoint, m.http_method as http_method, statuses
    ORDER BY m.endpoint
    """


    # [상위 호출 흐름 조회]
    # 특정 메서드를 '누가 호출하는지(Callers)' 역추적하여 전체 경로를 가져옵니다. (Upstream Analysis)
    # 핵심 로직: 화살표의 도착지(target)가 '나($method_id)'인 경우를 찾습니다. (Source -> Target(=Me))
    # 데이터 흐름이나 영향도 분석(Impact Analysis)에 사용됩니다.
    GET_UPSTREAM_IMPACT = """
    MATCH path = (source:METHOD)-[:CALLS*0..]->(target:METHOD)
    WHERE (elementId(target) = $method_id OR target.id = $method_id)
    RETURN path
    LIMIT 100
    """

    # [하위 호출 흐름 조회]
    # 특정 메서드가 '누구를 호출하는지(Callees)' 추적하여 전체 경로를 가져옵니다. (Downstream Analysis)
    # 핵심 로직: 화살표의 출발지(source)가 '나($method_id)'인 경우를 찾습니다. (Me -> Target)
    # 메서드의 실행 로직 파악이나 의존성 분석에 사용됩니다.
    GET_DOWNSTREAM_FLOW = """
    MATCH path = (source:METHOD)-[:CALLS*0..]->(target:METHOD)
    WHERE (elementId(source) = $method_id OR source.id = $method_id)
    RETURN path
    LIMIT 100
    """
    
    # --- Change Detection Helpers ---
    
    # [파일 해시 조회]
    # 특정 파일의 해시값을 조회하여 파일 변경 여부를 판단합니다.
    # Incremental Analysis(증분 분석)의 핵심 기준이 됩니다.
    GET_FILE_HASH = """
    MATCH (f:FILE {path: $file_path})
    RETURN f.hash as hash
    """

    # --- Status Management Queries ---
    
    # [삭제된 노드 정리]
    # 프로젝트 내에서 삭제된 노드(Method, Types)를 DB에서 완전히 제거(Hard Delete)합니다.
    # 'DELETED' 상태로 마킹된 후 일정 시간이 지났거나, 명시적 정리 요청 시 실행됩니다.
    # (FILE 삭제는 MARK_FILE_DELETED_AND_ISOLATE에서 즉시 수행됩니다)
    DELETE_PROJECT_DELETED_NODES = """
    MATCH (f:FILE {project: $project})
    
    // 1. Delete DELETED descendants (Methods, Types)
    WITH f
    OPTIONAL MATCH (f)-[:CONTAINS*]->(n)
    WHERE n.status = 'DELETED' AND NOT n:FILE
    DETACH DELETE n
    """
    
    # [프로젝트 파일 목록 및 해시 조회]
    # 전체 파일의 경로와 해시를 조회하여 로컬 파일시스템과 동기화 상태를 확인합니다.
    # 분석 시작 시(Snapshot 단계) 사용됩니다.
    GET_PROJECT_FILES_HASH = """
    MATCH (f:FILE)
    WHERE f.project = $project
    RETURN f.path as path, f.hash as hash
    """
    
    # [파일 삭제 (Mixed Strategy)]
    # 1. 파일(File)과 클래스(Type) 등 구조적인 노드는 즉시 삭제 (Hard Delete)
    # 2. 메서드(Method)는 'DELETED' 상태로 변경하여 보존 (Soft Delete & Orphan)
    #    -> 파일이 삭제되어도, 메서드의 존재 이력이나 ID 기반 조회는 가능하도록 함.
    MARK_FILE_DELETED_AND_ISOLATE = """
    MATCH (f:FILE {path: $path, project: $project})
    
    // 1. Identify descendant Methods to preserve
    OPTIONAL MATCH (f)-[:CONTAINS*]->(m:METHOD)
    SET m.status = 'DELETED'
    
    WITH f, collect(DISTINCT m) as methods
    
    // 2. Delete File and its descendants (Types, Fields), EXCLUDING Methods
    MATCH (f)-[:CONTAINS*0..]->(node)
    WHERE NOT node:METHOD
    DETACH DELETE node
    
    // 3. Isolate preserved Methods (remove outgoing calls)
    FOREACH (m IN methods | 
        FOREACH (r IN [(m)-[cw:CALLS]->() | cw] | DELETE r)
    )
    """
