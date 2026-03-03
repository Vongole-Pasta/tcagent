import logging
import json
from typing import List, Dict, Any, TypedDict
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END

from infra.db_client import DBClient
from graph_db.queries import CypherQueries

logger = logging.getLogger(__name__)

class HappyCaseState(TypedDict):
    """에이전트의 상태를 정의합니다."""
    source_method_ids: List[str]
    impact_groups: Dict[str, Any]
    contexts: Dict[str, Any]
    scenarios: List[Dict[str, Any]]
    errors: List[str]

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
        """변경된 메서드들로부터 영향받는 엔드포인트를 식별합니다."""
        impact_groups = {}
        for m_id in state['source_method_ids']:
            results = self.db_client.execute_query(
                CypherQueries.GET_PATHS_TO_ENDPOINTS,
                {"method_id": m_id}
            )
            for row in results:
                endpoint = row["endpoint"]
                if not endpoint: continue
                if endpoint not in impact_groups:
                    impact_groups[endpoint] = {
                        "url": endpoint,
                        "http_method": row["http_method"],
                        "name": row["endpoint_method_name"],
                        "paths": [],
                        "source_methods": set()
                    }
                impact_groups[endpoint]["paths"].append(row["path"])
                impact_groups[endpoint]["source_methods"].add(m_id)

        for ep in impact_groups:
            impact_groups[ep]["source_methods"] = list(impact_groups[ep]["source_methods"])

        return {"impact_groups": impact_groups}

    def retriever_node(self, state: HappyCaseState):
        """각 엔드포인트별 컨텍스트(코드, DTO)를 수집합니다."""
        contexts = {}
        for endpoint, group in state["impact_groups"].items():
            methods_context = []
            all_dtos = {}
            processed_signatures = set()
            public_dto_names = set()
            
            for path in group["paths"]:
                source_node = path.nodes[0]
                if "METHOD" in source_node.labels:
                    # 응답 DTO 추출
                    ret_type_obj = source_node.get("return_type")
                    ret_type = ret_type_obj.get("given") if isinstance(ret_type_obj, dict) else ret_type_obj
                    if ret_type and "ResponseEntity<" in ret_type:
                        try:
                            actual_dto = ret_type.split('<')[1].split('>')[0]
                            public_dto_names.add(actual_dto)
                        except: pass
                    elif ret_type and ret_type != "void":
                        public_dto_names.add(ret_type)
                    
                    # 요청 DTO 추출
                    param_query = """
                    MATCH (m:METHOD {signature: $signature})-[:HAS_PARAMETER]->(t:TYPE)
                    RETURN t.fullName as type_name LIMIT 1
                    """
                    param_res = self.db_client.execute_query(param_query, {"signature": source_node.get("signature")})
                    if param_res:
                        public_dto_names.add(param_res[0]["type_name"])

                for node in path.nodes:
                    if "METHOD" in node.labels:
                        sig = node.get("signature")
                        if sig not in processed_signatures:
                            methods_context.append({
                                "name": node.get("name"),
                                "signature": sig,
                                "source": node.get("source"),
                                "returnType": node.get("return_type") # Keep key as returnType for LLM consistency, but fetch return_type
                            })
                            processed_signatures.add(sig)
                            self._collect_dto_info(sig, all_dtos)
            
            # DTO 분류
            public_dtos = {}
            internal_dtos = {}
            for t_name, fields in all_dtos.items():
                is_public = any(p in t_name for p in public_dto_names)
                if is_public: public_dtos[t_name] = fields
                else: internal_dtos[t_name] = fields

            contexts[endpoint] = {
                "methods": methods_context,
                "public_dtos": public_dtos,
                "internal_dtos": internal_dtos,
                "public_dto_names": list(public_dto_names)
            }
        return {"contexts": contexts}

    def generator_node(self, state: HappyCaseState):
        """수집된 컨텍스트를 기반으로 Happy Case 전용 시나리오를 생성합니다."""
        scenarios = []
        errors = []
        tc_count = 1
        
        for endpoint, context in state["contexts"].items():
            group = state["impact_groups"][endpoint]
            
            prompt = f"""
당신은 백엔드 개발자이자 QA 엔지니어입니다. 제공된 코드 문맥을 분석하여 해당 API의 **Happy Case (성공 케이스, 200 OK)** 테스트 데이터를 생성해 주세요.

[대상 엔드포인트]
- URL: {endpoint}
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
- **헤더 분리**: `token`이나 `Authorization` 키와 같이 코드상에서 헤더(`response.setHeader`, `HttpHeaders` 등)로 처리되는 정보는 절대 응답 바디(JSON)에 포함하지 마세요.
- 만약 헤더 정보가 중요하다면, `expected_result` 문자열 내에 "Header: token=..." 과 같은 형식으로 바디 JSON 앞에 명시해 주세요.
- **Login 관련**: 로그인 성공 시 발급되는 토큰은 대부분 헤더에 위치합니다. 이를 바디에 섞지 않도록 각별히 주의하세요.

[요구사항]
1. 반드시 200 OK가 발생하는 성공 시나리오만 작성하세요.
2. `test_case`: "OOO 기능을 보장하기 위해 유효한 데이터를 전송함"과 같이 해당 API의 기능 위주로 한국어로 설명하세요.
3. `input_data`: API 호출에 필요한 입력 데이터 JSON을 작성하세요.
4. `expected_result`: 성공 시 예상되는 응답 데이터를 작성하세요. (헤더 정보가 있다면 바디 JSON 위에 명시)
"""
            try:
                result = self.structured_llm.invoke(prompt)
                scenarios.append({
                    "endpoint": endpoint,
                    "http_method": group['http_method'],
                    "test_case_id": f"TC-{tc_count:03d}", # LLM 결과 대신 코드에서 직접 부여
                    "test_case": result.test_case,
                    "input_data": result.input_data,
                    "expected_result": result.expected_result,
                    "trigger_methods": list(group['source_methods']), # 영향 준 메서드 ID들
                    "trigger_method_name": group['name']              # 엔드포인트 메서드명
                })
                tc_count += 1
            except Exception as e:
                logger.error(f"Failed for {endpoint}: {e}")
                errors.append(f"{endpoint}: {str(e)}")
                
        return {"scenarios": scenarios, "errors": errors}

    def _build_graph(self):
        workflow = StateGraph(HappyCaseState)
        workflow.add_node("planner", self.planner_node)
        workflow.add_node("retriever", self.retriever_node)
        workflow.add_node("generator", self.generator_node)
        workflow.set_entry_point("planner")
        workflow.add_edge("planner", "retriever")
        workflow.add_edge("retriever", "generator")
        workflow.add_edge("generator", END)
        return workflow.compile()

    def run(self, source_method_ids: List[str]):
        initial_state = {
            "source_method_ids": source_method_ids,
            "impact_groups": {},
            "contexts": {},
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
