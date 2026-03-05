class CypherQueries:
    """
    시스템에서 사용하는 주요 Cypher 쿼리문들을 중앙 관리하는 클래스입니다.
    문맥 검색, 호출 추적, 변경 감지 등의 쿼리가 포함되어 있습니다.
    """
    # --- Context Fetching Queries ---
    
    
    # [메서드 상세 조회]
    # 특정 메서드 ID를 입력받아 이름, 시그니처, 소스 코드를 반환합니다.
    # [단일 노드 메타데이터 조회]
    # 그래프 쿼리 결과가 없을 때(고립된 노드 등), 최소한 해당 노드는 보여주기 위해 사용합니다.
    # Usage: api/routers/graph.py:114, 145
    GET_NODE_METADATA = """
    MATCH (m:METHOD)
    WHERE (elementId(m) = $method_id OR m.id = $method_id)
    OPTIONAL MATCH (c:TYPE)-[:CONTAINS]->(m)
    RETURN m, c.name as className
    """
    
    # [메서드 컨텍스트 조회]
    # RAG(검색 증강 생성)를 위해 특정 메서드의 소스 코드와 주변 정보를 조회합니다.
    # Usage: api/routers/graph.py:165
    GET_METHOD_CONTEXT = """
    MATCH (m:METHOD)
    WHERE (elementId(m) = $method_id OR m.id = $method_id)
    RETURN m.name as name, m.signature as signature, m.source as source
    """
    

    

    
    # --- Impact Analysis Queries ---
    
    # [변경/신규 메서드 식별]
    # 에이전트가 테스트 대상으로 삼을 NEW/MODIFIED 상태의 메서드를 조회합니다.
    # Usage: core/agent/nodes.py:77
    GET_TARGET_METHODS = """
    MATCH (m:METHOD)
    WHERE m.status IN ['NEW', 'MODIFIED']
    RETURN elementId(m) as id, m.name as name, m.signature as signature, m.status as status
    """
    
    # [루트 메서드(진입점) 역추적]
    # 대상 메서드를 호출하는 최상위 루트 메서드를 찾습니다.
    # 다른 메서드에 의해 호출되지 않는 메서드(Controller 등)가 루트입니다.
    # Usage: core/agent/nodes.py:111
    TRACE_ROOT_METHODS = """
    MATCH path = (root:METHOD)-[:CALLS*0..]->(target:METHOD)
    WHERE (elementId(target) = $target_id)
      AND NOT ()-[:CALLS]->(root)
    RETURN root, target
    ORDER BY length(path) DESC
    """
    
    # [루트 메서드의 파라미터 조회]
    # 루트 메서드의 파라미터(JSON)와 HAS_PARAMETER로 연결된 TYPE의 필드 구조를 조회합니다.
    # params는 METHOD 노드에 JSON 문자열로 저장되어 있으므로 별도 파싱이 필요합니다.
    # Usage: core/agent/nodes.py:139
    GET_ROOT_PARAMETERS = """
    MATCH (m:METHOD)
    WHERE elementId(m) = $root_id
    OPTIONAL MATCH (m)-[:HAS_PARAMETER]->(t:TYPE)
    OPTIONAL MATCH (t)-[:CONTAINS]->(f:FIELD)
    RETURN m.params as params,
           collect(DISTINCT {type_name: t.name, type_qualname: t.qualname,
                             field_name: f.name, field_type: f.type}) as type_fields
    """



    # --- New Frontend Support Queries ---

    # [모든 메서드 목록 조회]
    # 프로젝트 내의 모든 메서드를 조회하여 검색 기능을 지원합니다.
    # [모든 메서드 목록 조회]
    # 프로젝트 내의 모든 메서드를 조회하여 검색 기능을 지원합니다.
    # Usage: api/routers/projects.py:38
    GET_ALL_METHODS = """
    MATCH (m:METHOD)<-[:CONTAINS]-(c:TYPE)
    RETURN elementId(m) as id, m.name as name, m.signature as signature, m.endpoint_uri as endpoint, m.http_method as http_method, m.status as status, c.name as class_name
    ORDER BY c.name, m.name
    """
    
    # [API 엔드포인트 목록 조회]
    # API 엔드포인트(URL) 정보를 가진 메서드만 필터링하여 조회합니다.
    # 각 엔드포인트가 호출하는 하위 메서드들의 상태(NEW/MODIFIED 등)를 집계하여 보여줍니다.
    # Usage: api/routers/projects.py:38
    GET_ALL_ENDPOINTS = """
    MATCH (m:METHOD)<-[:CONTAINS]-(c:TYPE)
    WHERE m.endpoint_uri IS NOT NULL
    OPTIONAL MATCH (m)-[:CALLS*0..]->(d:METHOD)
    WITH m, c, collect(DISTINCT d.status) as statuses
    RETURN elementId(m) as id, m.name as name, m.endpoint_uri as endpoint, m.http_method as http_method, statuses, c.name as class_name
    ORDER BY m.endpoint_uri
    """


    # [상위 호출 흐름 조회]
    # 특정 메서드를 '누가 호출하는지(Callers)' 역추적하여 전체 경로를 가져옵니다. (Upstream Analysis)
    # 핵심 로직: 화살표의 도착지(target)가 '나($method_id)'인 경우를 찾습니다. (Source -> Target(=Me))
    # 데이터 흐름이나 영향도 분석(Impact Analysis)에 사용됩니다.
    # Usage: api/routers/graph.py:104
    GET_UPSTREAM_IMPACT = """
    MATCH path = (source:METHOD)-[:CALLS*0..]->(target:METHOD)
    WHERE (elementId(target) = $method_id OR target.id = $method_id)
    WITH path LIMIT 100
    UNWIND nodes(path) as m
    OPTIONAL MATCH (c:TYPE)-[:CONTAINS]->(m)
    WITH path, collect({id: elementId(m), className: c.name}) as metadata
    RETURN path, metadata
    """

    # [하위 호출 흐름 조회]
    # 특정 메서드가 '누구를 호출하는지(Callees)' 추적하여 전체 경로를 가져옵니다. (Downstream Analysis)
    # 핵심 로직: 화살표의 출발지(source)가 '나($method_id)'인 경우를 찾습니다. (Me -> Target)
    # 메서드의 실행 로직 파악이나 의존성 분석에 사용됩니다.
    # Usage: api/routers/graph.py:136
    GET_DOWNSTREAM_FLOW = """
    MATCH path = (source:METHOD)-[:CALLS*0..]->(target:METHOD)
    WHERE (elementId(source) = $method_id OR source.id = $method_id)
    WITH path LIMIT 100
    UNWIND nodes(path) as m
    OPTIONAL MATCH (c:TYPE)-[:CONTAINS]->(m)
    WITH path, collect({id: elementId(m), className: c.name}) as metadata
    RETURN path, metadata
    """
    
    # --- Change Detection Helpers ---
    


    # --- Status Management Queries ---
    
    # [삭제된 노드 정리]
    # 프로젝트 내에서 삭제된 노드(Method, Types)를 DB에서 완전히 제거(Hard Delete)합니다.
    # 'DELETED' 상태로 마킹된 후 일정 시간이 지났거나, 명시적 정리 요청 시 실행됩니다.
    # (FILE 삭제는 MARK_FILE_DELETED_AND_ISOLATE에서 즉시 수행됩니다)
    # Usage: core/analysis/analyzer.py:47
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
    # Usage: core/analysis/analyzer.py:50
    GET_PROJECT_FILES_HASH = """
    MATCH (f:FILE)
    WHERE f.project = $project
    RETURN f.path as path, f.hash as hash
    """
    
    # [파일 삭제 (Mixed Strategy)]
    # 1. 파일(File)과 클래스(Type) 등 구조적인 노드는 즉시 삭제 (Hard Delete)
    # 2. 메서드(Method)는 'DELETED' 상태로 변경하여 보존 (Soft Delete & Orphan)
    #    -> 파일이 삭제되어도, 메서드의 존재 이력이나 ID 기반 조회는 가능하도록 함.
    # Usage: core/analysis/analyzer.py:129
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
