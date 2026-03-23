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
    RETURN elementId(m) as id, m.name as name, m.signature as signature, m.endpoint_uri as endpoint, m.http_method as http_method, m.status as status, c.name as class_name,m.source as source
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

    # [FE 전용 상위 호출 흐름 조회]
    # EXTERNAL_CALL 노드를 포함하여 상위 호출 경로를 조회합니다.
    GET_UPSTREAM_IMPACT_FOR_FE = """
    MATCH path = (source)-[:CALLS*0..]->(target:METHOD)
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

    # [FE 전용 하위 호출 흐름 조회]
    # EXTERNAL_CALL 노드를 포함하여 하위 호출 경로를 조회합니다.
    GET_DOWNSTREAM_FLOW_FOR_FE = """
    MATCH path = (source:METHOD)-[:CALLS*0..]->(target)
    WHERE (elementId(source) = $method_id OR source.id = $method_id)
    WITH path LIMIT 100
    UNWIND nodes(path) as m
    OPTIONAL MATCH (c:TYPE)-[:CONTAINS]->(m)
    WITH path, collect({id: elementId(m), className: c.name}) as metadata
    RETURN path, metadata
    """
    
    # 특정 메서드에서 엔드포인트까지의 경로 조회]
    # 특정 메서드($method_id)로부터 호출 가능한 모든 API 엔드포인트를 조회합니다.
    # Happy Case 에이전트의 영향도 분석(Planner)에 사용되며, 중간 경로(path)는 가져오지 않고 엔드포인트의 qualname만 반환합니다.
    # Usage: core/agent/happy_case_agent.py:39
    GET_PATHS_TO_ENDPOINTS = """
    MATCH (endpoint_m:METHOD)-[:CALLS*0..]->(target:METHOD)
    WHERE (elementId(target) = $method_id OR target.id = $method_id)
      AND endpoint_m.endpoint_uri IS NOT NULL
    RETURN endpoint_m.endpoint_uri as endpoint,
           endpoint_m.http_method as http_method,
           endpoint_m.name as endpoint_method_name,
           endpoint_m.qualname as qualname
    """

    # --- AS-IS Node Loading Queries (증분 분석 최적화) ---

    # [AS-IS TYPE 노드 로드]
    # 변경 없는(AS-IS) 파일의 TYPE 노드를 DB에서 로드합니다.
    # tree-sitter 파싱 대신 DB에서 이전 사이클의 노드 정보를 가져와 인메모리 인덱스를 구축합니다.
    # Usage: core/analysis/analyzer.py
    LOAD_ASIS_TYPES = """
    MATCH (f:FILE {project: $project})-[:CONTAINS]->(t:TYPE)
    WHERE f.path IN $paths
    RETURN t.qualname as qualname, t.name as name, t.kind as kind,
           t.constants as constants, t.supertypes as supertypes,
           f.path as file_path
    """

    # [AS-IS FIELD 노드 로드]
    # 변경 없는(AS-IS) 파일의 FIELD 노드를 DB에서 로드합니다.
    # Usage: core/analysis/analyzer.py
    LOAD_ASIS_FIELDS = """
    MATCH (f:FILE {project: $project})-[:CONTAINS]->(t:TYPE)-[:CONTAINS]->(field:FIELD)
    WHERE f.path IN $paths
    RETURN field.qualname as qualname, field.name as name,
           field.type as field_type, field.constraint as constraint,
           t.qualname as type_qualname
    """

    # [AS-IS METHOD 노드 로드]
    # 변경 없는(AS-IS) 파일의 METHOD 노드를 DB에서 로드합니다.
    # Usage: core/analysis/analyzer.py
    LOAD_ASIS_METHODS = """
    MATCH (f:FILE {project: $project})-[:CONTAINS]->(t:TYPE)-[:CONTAINS]->(m:METHOD)
    WHERE f.path IN $paths
    RETURN m.qualname as qualname, m.name as name, m.source as source,
           m.signature as signature, m.params as params, m.return_type as return_type,
           m.hash as method_hash, m.last_scan_id as scan_id,
           m.endpoint_uri as endpoint_uri, m.http_method as http_method,
           t.qualname as class_qualname
    """

    # [AS-IS METHOD status 갱신]
    # 증분 분석에서 AS-IS 파일은 write를 건너뛰므로, METHOD.status가 이전 사이클 값으로 남습니다.
    # 대시보드 표시를 위해 AS-IS 파일의 METHOD status를 명시적으로 'AS-IS'로 갱신합니다.
    # Usage: core/analysis/analyzer.py
    BATCH_UPDATE_ASIS_METHOD_STATUS = """
    UNWIND $paths AS path
    MATCH (f:FILE {path: path, project: $project})-[:CONTAINS]->(t:TYPE)-[:CONTAINS]->(m:METHOD)
    SET m.status = 'AS-IS'
    """

    # --- Analysis Pipeline Queries (analyzer.py) ---

    # [FILE 노드 일괄 Upsert]
    # 파일 메타데이터(경로, 이름, 해시, 언어)를 UNWIND 배치로 일괄 기록합니다.
    # 이미 존재하는 파일은 속성만 갱신됩니다.
    # Usage: core/analysis/analyzer.py
    BATCH_UPSERT_FILES = """
    UNWIND $batch AS row
    MERGE (f:FILE {path: row.path})
    SET f.name = row.name,
        f.hash = row.hash,
        f.language = row.language,
        f.project = row.project
    """

    # [메서드 일괄 가지치기 (Pruning)]
    # 이번 스캔(scan_id)에서 발견되지 않은 메서드를 DELETED로 마킹하고,
    # 호출 관계(CALLS)를 끊어 분석 결과 오염을 방지합니다.
    # Usage: core/analysis/analyzer.py
    BATCH_PRUNE_STALE_METHODS = """
    UNWIND $batch AS row
    MATCH (f:FILE {path: row.file_path})-[:CONTAINS*1..3]->(m:METHOD)
    WHERE m.last_scan_id <> row.scan_id
    SET m.status = 'DELETED'
    WITH m
    OPTIONAL MATCH (m)-[r:CALLS]-()
    DELETE r
    """

    # --- Writer Batch Queries (graph_writer.py) ---

    # [TYPE 노드 일괄 Upsert]
    # 파싱된 TYPE 노드를 UNWIND 배치로 일괄 기록합니다.
    # Usage: core/analysis/store/graph_writer.py
    BATCH_UPSERT_TYPES = """
    UNWIND $batch AS row
    MERGE (t:TYPE {qualname: row.qualname})
    SET t.name = row.name,
        t.kind = row.kind,
        t.constants = row.constants,
        t.supertypes = row.supertypes
    """

    # [FIELD 노드 일괄 Upsert]
    # 파싱된 FIELD 노드를 UNWIND 배치로 일괄 기록합니다.
    # Usage: core/analysis/store/graph_writer.py
    BATCH_UPSERT_FIELDS = """
    UNWIND $batch AS row
    MERGE (f:FIELD {qualname: row.qualname})
    SET f.name = row.name,
        f.type = row.type,
        f.constraint = row.constraint
    """

    # [METHOD 노드 일괄 Upsert]
    # 파싱된 METHOD 노드를 UNWIND 배치로 일괄 기록합니다.
    # 변경 감지: 해시 비교로 NEW/MODIFIED/AS-IS 상태를 자동 판별합니다.
    # Usage: core/analysis/store/graph_writer.py
    BATCH_UPSERT_METHODS = """
    UNWIND $batch AS row
    MERGE (m:METHOD {qualname: row.qualname})
    ON CREATE SET m.status = 'NEW'
    ON MATCH SET m.status = CASE
        WHEN m.hash = row.hash THEN 'AS-IS'
        ELSE 'MODIFIED'
    END
    SET m.name = row.name,
        m.signature = row.signature,
        m.source = row.source,
        m.hash = row.hash,
        m.params = row.params,
        m.return_type = row.return_type,
        m.endpoint_uri = row.endpoint_uri,
        m.http_method = row.http_method,
        m.last_scan_id = row.last_scan_id
    """

    # --- CONTAINS 구조 엣지 (graph_writer.py) ---

    # [FILE→CONTAINS→TYPE 엣지 일괄 생성]
    # Usage: core/analysis/store/graph_writer.py
    BATCH_UPSERT_FILE_CONTAINS_TYPE = """
    UNWIND $batch AS row
    MATCH (f:FILE {path: row.file_path})
    MATCH (t:TYPE {qualname: row.qualname})
    MERGE (f)-[:CONTAINS]->(t)
    """

    # [TYPE→CONTAINS→FIELD 엣지 일괄 생성]
    # Usage: core/analysis/store/graph_writer.py
    BATCH_UPSERT_TYPE_CONTAINS_FIELD = """
    UNWIND $batch AS row
    MATCH (t:TYPE {qualname: row.type_qualname})
    MATCH (f:FIELD {qualname: row.qualname})
    MERGE (t)-[:CONTAINS]->(f)
    """

    # [TYPE→CONTAINS→METHOD 엣지 일괄 생성]
    # Usage: core/analysis/store/graph_writer.py
    BATCH_UPSERT_TYPE_CONTAINS_METHOD = """
    UNWIND $batch AS row
    MATCH (t:TYPE {qualname: row.class_qualname})
    MATCH (m:METHOD {qualname: row.qualname})
    MERGE (t)-[:CONTAINS]->(m)
    """

    # [FIELD→CONTAINS→TYPE 엣지 일괄 생성]
    # 필드가 참조하는 타입과의 관계 (예: UserService 필드 → UserService 타입)
    # Usage: core/analysis/store/graph_writer.py
    BATCH_UPSERT_FIELD_CONTAINS_TYPE = """
    UNWIND $batch AS row
    MATCH (f:FIELD {qualname: row.field_qualname})
    MATCH (t:TYPE {qualname: row.type_qualname})
    MERGE (f)-[:CONTAINS]->(t)
    """

    # --- 의미 엣지 (graph_writer.py) ---

    # [HAS_PARAMETER 엣지 일괄 생성]
    # 메서드 → 파라미터 타입 관계를 일괄 기록합니다.
    # Usage: core/analysis/store/graph_writer.py
    BATCH_UPSERT_PARAMETER_EDGES = """
    UNWIND $batch AS row
    MATCH (m:METHOD {qualname: row.method_qualname})
    MATCH (t:TYPE {qualname: row.type_qualname})
    MERGE (m)-[:HAS_PARAMETER]->(t)
    """

    # [RETURNS 엣지 일괄 생성]
    # 메서드 → 리턴 타입 관계를 일괄 기록합니다.
    # Usage: core/analysis/store/graph_writer.py
    BATCH_UPSERT_RETURN_EDGES = """
    UNWIND $batch AS row
    MATCH (m:METHOD {qualname: row.method_qualname})
    MATCH (t:TYPE {qualname: row.type_qualname})
    MERGE (m)-[:RETURNS]->(t)
    """

    # [CALLS 엣지 일괄 생성 (프로젝트 내부)]
    # 프로젝트 내 메서드 간 호출 관계를 일괄 기록합니다.
    # Usage: core/analysis/store/graph_writer.py
    BATCH_UPSERT_CALLS = """
    UNWIND $batch AS row
    MATCH (caller:METHOD {qualname: row.caller_qualname})
    MATCH (callee:METHOD {qualname: row.callee_qualname})
    MERGE (caller)-[:CALLS]->(callee)
    """

    # [CALLS 엣지 일괄 생성 (외부 호출)]
    # 프로젝트 외부 라이브러리 메서드 호출을 EXTERNAL_CALL 노드로 기록합니다.
    # Usage: core/analysis/store/graph_writer.py
    BATCH_UPSERT_EXTERNAL_CALLS = """
    UNWIND $batch AS row
    MATCH (caller:METHOD {qualname: row.caller_qualname})
    MERGE (ext:EXTERNAL_CALL {qualname: row.ext_qualname})
    SET ext.name = row.name,
        ext.signature = row.signature
    MERGE (caller)-[:CALLS]->(ext)
    """

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
    
    # [삭제 파일 처리 — 2-Phase Mixed Strategy]
    # 파일 삭제 시 METHOD는 이력 조회를 위해 고아 노드로 보존하고,
    # FILE/TYPE/FIELD 등 구조적 노드는 즉시 삭제합니다.
    # UNWIND + DETACH DELETE 조합의 안정성을 위해 2개 쿼리로 분리합니다.
    # Usage: core/analysis/analyzer.py

    # Phase 1: 삭제 파일의 METHOD를 DELETED로 마킹하고 CALLS 관계를 끊어 격리합니다.
    BATCH_ISOLATE_DELETED_FILE_METHODS = """
    UNWIND $batch AS row
    MATCH (f:FILE {path: row.path, project: row.project})-[:CONTAINS*]->(m:METHOD)
    SET m.status = 'DELETED'
    WITH m
    OPTIONAL MATCH (m)-[r:CALLS]->()
    DELETE r
    """

    # Phase 2: 삭제 파일과 구조적 자식(TYPE, FIELD)을 DB에서 영구 삭제합니다.
    # METHOD는 Phase 1에서 이미 격리되었으므로 제외합니다.
    BATCH_DELETE_FILE_STRUCTURES = """
    UNWIND $batch AS row
    MATCH (f:FILE {path: row.path, project: row.project})-[:CONTAINS*0..]->(node)
    WHERE NOT node:METHOD
    DETACH DELETE node
    """
