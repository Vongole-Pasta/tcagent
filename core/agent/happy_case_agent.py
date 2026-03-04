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
    related_signatures: List[str]  # Path 노드들의 시그니처 목록
    source_methods: List[str]     # 영향을 준 소스 메서드 ID 목록

class HappyCaseState(TypedDict):
    """
    에이전트의 전체 State를 정의합니다.
    NotRequired를 사용하여 필수 입력값이 아닌 필드들을 구분합니다.
    """
    source_method_ids: List[str]                 # 입력: 영향도 분석 시작점 (또는 직접 선택한 엔드포인트)
    
    impact_groups: NotRequired[Dict[str, ImpactGroup]] # 분석 결과: 식별된 엔드포인트 그룹
    worker_results: Annotated[NotRequired[List[Dict[str, Any]]], operator.add] # 워커 중간 결과물
    scenarios: NotRequired[List[Dict[str, Any]]]       # 최종 결과물 (ID 부여 등 전처리 완료)
    errors: Annotated[NotRequired[List[str]], operator.add]

class WorkerState(TypedDict):
    """
    개별 엔드포인트 작업을 위한 State입니다.
    데이터 전송 오버헤드를 줄이기 위해 필요한 필드만 포함합니다.
    """
    endpoint_url: str
    group: ImpactGroup

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
                        "related_signatures": [],"source_methods": []
                    }
                
                # Path 객체에서 시그니처만 추출
                path_signatures = [node.get("signature") for node in row["path"].nodes if "METHOD" in node.labels]
                
                existing_sigs = set(impact_groups[group_key]["related_signatures"])
                impact_groups[group_key]["related_signatures"].extend([s for s in path_signatures if s not in existing_sigs])
                
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

    def generator_worker_node(self, state: WorkerState):
        """
        정제된 시그니처 목록을 사용하여 컨텍스트 수집(Retriever) 및 시나리오 생성(Generator)을 수행합니다.
        Neo4j Path 객체 대신 문자열 리스트를 사용하여 데이터 파싱 비용을 줄입니다.
        """
        endpoint_url = state["endpoint_url"]
        group = state["group"]
        
        # 1. 컨텍스트 수집 (시그니처 기반)
        methods_context = []
        all_dtos = {}
        processed_signatures = set()
        public_dto_names = set()
        
        for sig in group["related_signatures"]:
            if sig in processed_signatures: continue
            
            # 메서드 기본 정보 조회
            method_res = self.db_client.execute_query(
                "MATCH (m:METHOD {signature: $signature}) RETURN m", 
                {"signature": sig}
            )
            if not method_res: continue
            method_node = method_res[0]["m"]
            
            # 요청/응답 DTO 이름 추출
            ret_type_obj = method_node.get("return_type")
            ret_type = ret_type_obj.get("given") if isinstance(ret_type_obj, dict) else ret_type_obj
            if ret_type and "ResponseEntity<" in ret_type:
                try: actual_dto = ret_type.split('<')[1].split('>')[0]; public_dto_names.add(actual_dto)
                except: pass
            elif ret_type and ret_type != "void":
                public_dto_names.add(ret_type)
            
            param_query = "MATCH (m:METHOD {signature: $signature})-[:HAS_PARAMETER]->(t:TYPE) RETURN t.fullName as type_name LIMIT 1"
            param_res = self.db_client.execute_query(param_query, {"signature": sig})
            if param_res: public_dto_names.add(param_res[0]["type_name"])

            # 컨텍스트 추가
            methods_context.append({
                "name": method_node.get("name"),
                "signature": sig,
                "source": method_node.get("source"),
                "returnType": method_node.get("return_type")
            })
            processed_signatures.add(sig)
            self._collect_dto_info(sig, all_dtos)
        
        # DTO 분류 (Public vs Internal)
        public_dtos = {}
        internal_dtos = {}
        for t_name, fields in all_dtos.items():
            if any(p in t_name for p in public_dto_names): public_dtos[t_name] = fields
            else: internal_dtos[t_name] = fields

        context = {
            "methods": methods_context,
            "public_dtos": public_dtos,
            "internal_dtos": internal_dtos
        }

        # 2. 시나리오 생성
        prompt = f"""
        당신은 백엔드 개발자이자 QA 엔지니어입니다. 제공된 코드 문맥을 분석하여 해당 API의 **Happy Case (성공 케이스, 200 OK)** 테스트 데이터를 생성해 주세요.

        [대상 엔드포인트]
        - URL: {endpoint_url}
        - Method: {group['http_method']}
        - Name: {group['name']}

        [비즈니스 로직 문맥]
        {json.dumps(context['methods'], indent=2, ensure_ascii=False)}

        [Public API DTO 구조 (필수 준수)]
        {json.dumps(context['public_dtos'], indent=2, ensure_ascii=False)}

        [Internal Data structures (참고용 컨텍스트)]
        {json.dumps(context['internal_dtos'], indent=2, ensure_ascii=False)}

        [DTO 매핑 및 헤더 지침]
        - **중요**: `expected_result` (응답 바디)에는 오직 **[Public API DTO 구조]**에 정의된 필드만 포함해야 합니다.
        - **헤더 지침**: 
          - `Content-Type: application/json`과 같이 모든 응답에 공통적이고 당연한 정보는 절대 포함하지 마세요.
          - `Location` 헤더(리소스 생성 시)나 `Set-Cookie` 등 **비즈니스적으로 의미 있는 특정 헤더**가 코드상에서 확인될 경우에만, `expected_result`의 JSON 바디 앞에 "Header: Key=Value" 형식으로 명시하세요.
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
            logger.error(f"Failed for {endpoint_url}: {e}")
            return {"errors": [f"{endpoint_url}: {str(e)}"]}

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
            """
            planner 노드 종료 후 호출되는 매핑 함수입니다.
            식별된 각 엔드포인트마다 새로운 generator_worker 노드를 병렬로 생성(Send)합니다.
            """
            impact_groups = state.get("impact_groups", {})
            if not impact_groups:
                logger.warning("Sending to END because no impact groups found.")
                # Send API는 빈 리스트 반환 시 다음 노드로 가지 않음. 
                # 하지만 conditional edge 자체에서 END로 명시적으로 보낼 수도 있음.
                return []
            
            logger.info(f"Sending to {len(impact_groups)} workers for endpoints: {list(impact_groups.keys())}")
            return [
                Send("generator_worker", {"endpoint_url": group["url"], "group": group})
                for group in impact_groups.values()
            ]

        workflow = StateGraph(HappyCaseState)
        workflow.add_node("planner", self.planner_node)
        workflow.add_node("generator_worker", self.generator_worker_node)
        workflow.add_node("formatter", self.formatter_node) # 마무리 노드 추가
        
        workflow.set_entry_point("planner")
        workflow.add_conditional_edges("planner", continue_to_workers, ["generator_worker"])
        
        # worker들이 모두 종료되면 formatter로 집결
        workflow.add_edge("generator_worker", "formatter")
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
        query = """
        MATCH (m:METHOD {signature: $signature})
        OPTIONAL MATCH (m)-[:HAS_PARAMETER]->(pt:TYPE)
        OPTIONAL MATCH (pt)-[:CONTAINS]->(pf:FIELD)
        OPTIONAL MATCH (m)-[:RETURNS]->(rt:TYPE)
        OPTIONAL MATCH (rt)-[:CONTAINS]->(rf:FIELD)
        RETURN 
            pt.fullName as pt_name, pf.name as pf_name, pf.type as pf_type,
            rt.fullName as rt_name, rf.name as rf_name, rf.type as rf_type
        """
        results = self.db_client.execute_query(query, {"signature": method_signature})
        for row in results:
            if row["pt_name"]:
                t_name = row["pt_name"]
                if t_name not in dtos_context: dtos_context[t_name] = []
                if row["pf_name"] and not any(f["name"] == row["pf_name"] for f in dtos_context[t_name]):
                    # Check if pf_type is dict (TypeInfo)
                    p_f_type = row["pf_type"].get("given") if isinstance(row["pf_type"], dict) else row["pf_type"]
                    dtos_context[t_name].append({"name": row["pf_name"], "type": p_f_type})
            if row["rt_name"]:
                t_name = row["rt_name"]
                if t_name not in dtos_context: dtos_context[t_name] = []
                if row["rf_name"] and not any(f["name"] == row["rf_name"] for f in dtos_context[t_name]):
                    # Check if rf_type is dict (TypeInfo)
                    r_f_type = row["rf_type"].get("given") if isinstance(row["rf_type"], dict) else row["rf_type"]
                    dtos_context[t_name].append({"name": row["rf_name"], "type": r_f_type})
