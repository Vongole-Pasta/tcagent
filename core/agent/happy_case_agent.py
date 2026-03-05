import logging
import json
import operator
from typing import List, Dict, Any, TypedDict, Annotated, NotRequired
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langgraph.constants import Send

from infra.db_client import DBClient
from graph_db.queries import CypherQueries

logger = logging.getLogger(__name__)

class ImpactGroup(TypedDict):
    """엔드포인트별 식별 및 컨텍스트 정보 (Path 객체 제외)"""
    url: str
    http_method: str
    name: str
    endpoint_signatures: List[str]  # 엔드포인트 메서드 시그니처 목록
    source_methods: List[str]     # 영향을 준 소스 메서드 ID 목록

class HappyCaseState(TypedDict):
    """
    에이전트의 전체 State를 정의합니다.
    NotRequired를 사용하여 필수 입력값이 아닌 필드들을 구분합니다.
    """
    source_method_ids: List[str]                 # 입력: 영향도 분석 시작점 (또는 직접 선택한 엔드포인트)
    
    impact_groups: NotRequired[Dict[str, ImpactGroup]] # 분석 결과: 식별된 엔드포인트 그룹 (key: "HTTP_METHOD:URL")
    # Annotated[..., operator.add]: 병렬 워커들이 각자 반환하는 리스트를 덮어쓰지 않고 자동으로 누적(append)합니다.
    worker_results: Annotated[NotRequired[List[Dict[str, Any]]], operator.add] # 각 워커의 중간 결과물 (검증 통과 후 집계)
    scenarios: NotRequired[List[Dict[str, Any]]]       # 최종 결과물 (TC-001 등 ID 부여 완료)
    # errors도 리듀서 적용: 여러 워커에서 발생한 에러를 하나의 리스트로 합칩니다.
    errors: Annotated[NotRequired[List[str]], operator.add]

class WorkerState(TypedDict):
    """
    개별 엔드포인트 작업을 위한 State입니다.
    retriever -> generator 순서로 데이터가 전달됩니다.
    """
    endpoint_url: str
    group: ImpactGroup
    context: NotRequired[Dict[str, Any]]         # retriever가 수집한 메서드/DTO 컨텍스트
    worker_results: Annotated[NotRequired[List[Dict[str, Any]]], operator.add]  # 생성된 최종 결과 (시나리오)
    errors: Annotated[NotRequired[List[str]], operator.add]  # 워커에서 발생한 에러 기록

class HappyCaseOutput(BaseModel):
    """LLM이 생성할 Happy Case 시나리오 구조 (요구사항 반영)"""
    test_case: str = Field(description="테스트하려는 API가 어떤 기능인지 설명 (Happy Case)")
    input_data: str = Field(description="입력 데이터 예시 (JSON 형식 문자열 등)")
    expected_result: str = Field(description="예상 결과 예시 (JSON 형식 문자열 등)")

class HappyCaseAgent:
    def __init__(self, db_client: DBClient):
        self.db_client = db_client
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
        self.structured_llm = self.llm.with_structured_output(HappyCaseOutput)
        self.graph = self._build_graph()

    def planner_node(self, state: HappyCaseState):
        """
        입력된 메서드들로부터 영향을 받는(또는 직접 선택된) 엔드포인트를 식별합니다.
        """
        raw_ids = state.get('source_method_ids', [])
        clean_ids = self._sanitize_ids(raw_ids)
        logger.info(f"Cleaned IDs for planning: {clean_ids}")
        
        # 2. 엔드포인트 식별 및 경로 시그니처 추출
        impact_groups: Dict[str, ImpactGroup] = {}
        for m_id in clean_ids:
            # GET_PATHS_TO_ENDPOINTS: m_id를 향해 호출하거나 m_id 자체가 엔드포인트인 경우 모두 식별
            results = self.db_client.execute_query(
                CypherQueries.GET_PATHS_TO_ENDPOINTS,
                {"method_id": m_id}
            )
            
            for row in results:
                endpoint = row["endpoint"]
                http_method = row["http_method"]
                if not endpoint: continue
                
                # 같은 URL이라도 HTTP Method가 다르면 별개의 엔드포인트로 취급
                group_key = f"{http_method}:{endpoint}"
                
                if group_key not in impact_groups:
                    impact_groups[group_key] = {
                        "url": endpoint,"http_method": http_method,"name": row["endpoint_method_name"],
                        "endpoint_signatures": [],"source_methods": []
                    }
                
                # DB에서 전달받은 최종 엔드포인트 메서드의 시그니처만 바로 사용합니다.
                # DB 단에서부터 불필요한 중간 경로를 생략하여 네트워크 및 메모리 낭비를 줄입니다.
                endpoint_signature = row.get("signature")
                
                # 이미 추가된 시그니처는 건너뛰어 같은 메서드가 여러 경로로 발견돼도 중복 등록하지 않습니다.
                existing_sigs = set(impact_groups[group_key]["endpoint_signatures"])
                if endpoint_signature and endpoint_signature not in existing_sigs:
                    impact_groups[group_key]["endpoint_signatures"].append(endpoint_signature)
                
                if m_id not in impact_groups[group_key]["source_methods"]:
                    impact_groups[group_key]["source_methods"].append(m_id)

        return {
            "source_method_ids": clean_ids, 
            "impact_groups": impact_groups
        }

    def _sanitize_ids(self, ids: List[str]) -> List[str]:
        """ID 리스트를 정제합니다 (따옴표 제거 등)."""
        clean = []
        for rid in ids:
            if not isinstance(rid, str): continue
            rid = rid.strip()
            if rid.startswith('[') and rid.endswith(']'):
                try:
                    parsed = json.loads(rid)
                    if isinstance(parsed, list):
                        clean.extend([str(i).strip(" '\"") for i in parsed]); continue
                except: pass
            clean.append(rid.strip(" '\"[]"))
        return list(set(clean))

    def retriever_worker_node(self, state: WorkerState):
        """
        DB에서 메서드/DTO 컨텍스트를 수집합니다.
        루프가 발생하더라도 이 노드는 재실행되지 않아 중복 DB 조회를 방지합니다.
        """
        group = state["group"]
        methods_context = []
        all_dtos = {}
        processed_signatures = set()

        for sig in group["endpoint_signatures"]:
            if sig in processed_signatures: continue

            method_res = self.db_client.execute_query(
                "MATCH (m:METHOD {signature: $signature}) RETURN m",
                {"signature": sig}
            )
            if not method_res: continue
            method_node = method_res[0]["m"]

            # 파라미터 정보 추출 (LLM 프롬프트용)
            params_info = method_node.get("params", [])     # Method 노드에 속성(params)으로 저장된 파라미터 정보
            if isinstance(params_info, str):
                try: params_info = json.loads(params_info)
                except: params_info = []

            methods_context.append({
                "name": method_node.get("name"),
                "signature": sig,
                "source": method_node.get("source"),
                "params": params_info,
                "returnType": method_node.get("return_type")
            })
            processed_signatures.add(sig)
            # _collect_dto_info를 통해 파라미터/반환 타입 및 중첩 DTO들의 필드 구조를 수집합니다.
            self._collect_dto_info(sig, all_dtos)

        return {
            "context": {"methods": methods_context, "dto_context": all_dtos}
        }

    def generator_worker_node(self, state: WorkerState):
        """
        수집된 컨텍스트로 LLM을 호출하여 시나리오를 생성합니다.
        """
        endpoint_url = state["endpoint_url"]
        group = state["group"]
        context = state.get("context", {})

        prompt = f"""
        당신은 백엔드 개발자이자 QA 엔지니어입니다. 제공된 코드 문맥을 분석하여 해당 API의 **Happy Case (성공 케이스, 200 OK)** 테스트 데이터를 생성해 주세요.

        [대상 엔드포인트]
        - URL: {endpoint_url}
        - Method: {group['http_method']}
        - Name: {group['name']}

        [비즈니스 로직 문맥]
        {json.dumps(context.get('methods', []), indent=2, ensure_ascii=False)}

        [API DTO 구조 (필수 준수)]
        {json.dumps(context.get('dto_context', {}), indent=2, ensure_ascii=False)}

        [DTO 매핑 및 호출 지침]
        - **중요**: `expected_result` (응답 바디)에는 오직 **[API DTO 구조]**에 정의된 필드만 포함해야 합니다.
        - **입력 데이터(input_data) 생성 지침**:
          - 엔드포인트 메서드의 파라미터 목록(`params`)을 보고 각 데이터의 소스를 판단하세요.
          - **Body**: DTO 타입이거나 `@RequestBody`인 경우 JSON 바디로 작성하세요.
          - **Header**: `@RequestHeader` 또는 이름/타입상 헤더로 추정되는 경우, `input_data` 최상단에 "Header: Key=Value" 형식으로 작성하세요.
          - **Path**: `@PathVariable` 또는 URL 패턴(`{id}` 등)과 일치하는 경우, "Path: Key=Value" 형식으로 작성하세요.
          - **Query**: `@RequestParam` 또는 기타 원시 타입인 경우, "Query: Key=Value" 형식으로 작성하세요.
          - 여러 소스가 섞여 있다면 각각 명시한 후 마지막에 바디 JSON을 작성하세요.
        - **예상 결과(expected_result) 생성 지침**:
          - `Content-Type: application/json`과 같이 당연한 정보는 생략하세요.
          - `Location` 헤더(리소스 생성 시)나 `Set-Cookie` 등 **비즈니스적으로 의미 있는 특정 응답 헤더**가 코드상에서 확인될 경우에만, JSON 바디 앞에 "Header: Key=Value" 형식으로 명시하세요.
        - **보안/토큰**: `token`이나 `Authorization`과 같은 보안 정보는 헤더로 명시하되, 실제 값이 아닌 `<TOKEN>`과 같은 플레이스홀더를 사용하세요.

        [요구사항]
        1. 반드시 200 OK(또는 생성 시 201 Created)가 발생하는 성공 시나리오만 작성하세요.
        2. `test_case`: "OOO 기능을 보장하기 위해 유효한 데이터를 전송함"과 같이 해당 API의 기능 위주로 한국어로 설명하세요.
        3. `input_data`: API 호출에 필요한 입력 데이터 JSON을 작성하세요.
        4. `expected_result`: 성공 시 예상되는 응답 데이터를 작성하세요. (의미 있는 헤더가 있다면 JSON 위에 명시)
        """

        try:
            result = self.structured_llm.invoke(prompt)
            scenario = {
                "endpoint": endpoint_url,
                "http_method": group['http_method'],
                "test_case": result.test_case,
                "input_data": result.input_data,
                "expected_result": result.expected_result
            }
            return {"worker_results": [scenario]}
        except Exception as e:
            logger.error(f"LLM generation failed for {endpoint_url}: {e}")
            return {"errors": [f"[{endpoint_url}] LLM 호출 오류: {str(e)}"]}


    def formatter_node(self, state: HappyCaseState):
        """
        수집된 모든 중간 결과(`worker_results`)에 최종 ID를 부여하여 `scenarios`에 저장합니다.
        """
        raw_results = state.get("worker_results", [])
        scenarios = []
        for i, scenario in enumerate(raw_results):
            # 복사하여 ID 부여
            final_scen = scenario.copy()
            final_scen["test_case_id"] = f"TC-{i+1:03d}"
            scenarios.append(final_scen)
        
        return {"scenarios": scenarios}

    def _build_graph(self):

        def continue_to_workers(state: HappyCaseState):
            """planner 종료 후 각 엔드포인트마다 독립적인 워커 서브 그래프를 병렬 실행합니다."""
            impact_groups = state.get("impact_groups", {})
            if not impact_groups:
                logger.warning("No impact groups found, skipping to END.")
                return []
            logger.info(f"Dispatching {len(impact_groups)} workers: {list(impact_groups.keys())}")
            return [
                Send("worker", {"endpoint_url": group["url"], "group": group})
                for group in impact_groups.values()
            ]

        # --- 서브 그래프: 단일 엔드포인트 처리 (retriever -> generator) ---
        worker_builder = StateGraph(WorkerState)
        worker_builder.add_node("retriever", self.retriever_worker_node)
        worker_builder.add_node("generator", self.generator_worker_node)

        worker_builder.set_entry_point("retriever")
        worker_builder.add_edge("retriever", "generator")
        worker_builder.add_edge("generator", END)

        compiled_worker = worker_builder.compile()

        # --- 메인 그래프 ---
        workflow = StateGraph(HappyCaseState)
        workflow.add_node("planner", self.planner_node)
        workflow.add_node("worker", compiled_worker)
        workflow.add_node("formatter", self.formatter_node)

        workflow.set_entry_point("planner")
        workflow.add_conditional_edges("planner", continue_to_workers, ["worker"])
        workflow.add_edge("worker", "formatter")
        workflow.add_edge("formatter", END)

        return workflow.compile()

    def run(self, source_method_ids: List[str]):
        """
        에이전트를 실행하여 병렬로 Happy Case 시나리오를 생성합니다.
        """
        initial_state = {
            "source_method_ids": source_method_ids,
            "impact_groups": {},
            "worker_results": [],
            "scenarios": [],
            "errors": []
        }
        return self.graph.invoke(initial_state)

    def _collect_dto_info(self, method_signature, dtos_context):
        """
        특정 메서드의 파라미터/반환 타입 및 그로부터 도달 가능한 중첩 DTO(최대 5단계)의 필드 구조를 수집합니다.
        결과는 dtos_context 딕셔너리에 {타입명: [{name, type}, ...]} 형태로 누적됩니다.
        """
        # 1. METHOD -> (HAS_PARAMETER|RETURNS) -> TYPE (직접 관계)
        # 2. METHOD -> (CONTAINS) -> PARAMETER -> (OF_TYPE) -> TYPE (실제 스캔 구조)
        # 위 두 경로를 모두 지원하여 root TYPE을 찾고, 거기서부터 재귀 탐색합니다.
        query = """
        MATCH (m:METHOD {signature: $signature})
        OPTIONAL MATCH (m)-[:HAS_PARAMETER|RETURNS]->(root1:TYPE)
        OPTIONAL MATCH (m)-[:CONTAINS]->(:PARAMETER)-[:OF_TYPE]->(root2:TYPE)
        WITH DISTINCT root1, root2
        UNWIND [root1, root2] as root
        WITH DISTINCT root WHERE root IS NOT NULL
        OPTIONAL MATCH path = (root)-[:CONTAINS|OF_TYPE *0..10]->(t:TYPE)
        WITH DISTINCT t
        WHERE t IS NOT NULL
        MATCH (t)-[:CONTAINS]->(f:FIELD)
        RETURN t.fullName as type_name, f.name as field_name, f.type as field_type
        """
        results = self.db_client.execute_query(query, {"signature": method_signature})
        for row in results:
            t_name = row["type_name"]
            if t_name not in dtos_context:
                dtos_context[t_name] = []
            
            if row["field_name"] and not any(f["name"] == row["field_name"] for f in dtos_context[t_name]):
                # TypeInfo 객체(dict)인 경우 "given" 키에서 실제 타입 문자열을 꺼냅니다.
                f_type_obj = row["field_type"]
                if isinstance(f_type_obj, str):
                    try: f_type_obj = json.loads(f_type_obj)
                    except: pass
                f_type = f_type_obj.get("given") if isinstance(f_type_obj, dict) else f_type_obj
                dtos_context[t_name].append({"name": row["field_name"], "type": f_type})
