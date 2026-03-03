import logging
import json
from typing import List, Dict, Any, TypedDict, Annotated
from operator import add

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from infra.db_client import DBClient
from graph_db.queries import CypherQueries

logger = logging.getLogger(__name__)

class IntegrationState(TypedDict):
    """에이전트의 상태를 정의합니다."""
    # 변경된 메서드들의 목록 (ID 또는 Signature)
    source_method_ids: List[str]
    # 엔드포인트별로 그룹화된 영향 경로 및 원인 메서드들
    impact_groups: Dict[str, Any]
    contexts: Dict[str, Any]
    scenarios: List[Dict[str, Any]]
    # 루프 제어를 위한 필드
    iterations: int
    max_iterations: int
    validation_results: List[Dict[str, Any]]
    errors: List[str]
    next_step: str

class RequestDetail(BaseModel):
    payload: str = Field(description="샘플 Request JSON 페이로드 (문자열)")
    headers: str = Field(description="샘플 Request HTTP 헤더 (문자열, 예: Authorization: ...)")

class ResponseDetail(BaseModel):
    payload: str = Field(description="샘플 Response JSON 페이로드 (문자열)")
    headers: str = Field(description="샘플 Response HTTP 헤더 (문자열, 예: token: ...)")

class ScenarioOutput(BaseModel):
    """LLM이 생성할 시나리오의 구조입니다."""
    scenario: str = Field(description="테스트 시나리오 설명")
    expected_result: str = Field(description="기대 결과")
    request: RequestDetail
    response: ResponseDetail

class ValidatorOutput(BaseModel):
    """Validator 노드의 검증 결과 구조입니다."""
    is_valid: bool = Field(description="시나리오가 모든 검증 기준을 충족하는지 여부")
    feedback: str = Field(description="결함이 발견된 경우 구체적인 수정 지침 (없으면 빈 문자열)")
    endpoint: str = Field(description="검증 대상 엔드포인트")

class IntegrationAgent:
    def __init__(self, db_client: DBClient):
        self.db_client = db_client
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.2)
        # strict=False를 명시적으로 주거나, payload를 string으로 받아서 파싱하는 전략 사용
        self.structured_llm = self.llm.with_structured_output(ScenarioOutput)
        self.validator_llm = self.llm.with_structured_output(ValidatorOutput)
        self.graph = self._build_graph()

    def planner_node(self, state: IntegrationState):
        """변경된 메서드들로부터 영향받는 엔드포인트를 그룹화합니다."""
        logger.info(f"Planning for source methods: {state['source_method_ids']}")
        
        impact_groups = {}
        
        for m_id in state['source_method_ids']:
            results = self.db_client.execute_query(
                CypherQueries.GET_PATHS_TO_ENDPOINTS,
                {"method_id": m_id}
            )
            
            for row in results:
                endpoint = row["endpoint"]
                # 엔드포인트가 비어있거나 None인 경우 스킵
                if not endpoint:
                    continue
                    
                if endpoint not in impact_groups:
                    impact_groups[endpoint] = {
                        "url": endpoint,
                        "http_method": row["http_method"],
                        "name": row["endpoint_method_name"],
                        "paths": [],
                        "source_methods": set(),
                        "source_method_names": set()
                    }
                
                impact_groups[endpoint]["paths"].append(row["path"])
                impact_groups[endpoint]["source_methods"].add(m_id) # 원인 메서드 추적
                
                # 시그니처나 이름을 통해 읽기 쉬운 메서드 이름 파싱
                sig = row.get("target_signature")
                name = row.get("target_name")
                if sig:
                    sig_parts = sig.split('(')
                    if len(sig_parts) > 1:
                        class_method = sig_parts[0].split('.')[-2:]
                        display_name = '.'.join(class_method)
                    else:
                        display_name = sig.split('.')[-1]
                    impact_groups[endpoint]["source_method_names"].add(display_name)
                elif name:
                    impact_groups[endpoint]["source_method_names"].add(name)
                else:
                    impact_groups[endpoint]["source_method_names"].add(m_id)
            
        if not impact_groups:
            return {"errors": ["No reachable endpoints found from changes."], "next_step": END}
            
        # set을 list로 변환 (JSON 직렬화 및 상태 관리를 위해)
        for ep in impact_groups:
            impact_groups[ep]["source_methods"] = list(impact_groups[ep]["source_methods"])
            if "source_method_names" in impact_groups[ep]:
                impact_groups[ep]["source_method_names"] = list(impact_groups[ep]["source_method_names"])

        # LangGraph Studio 등에서 초기 상태 없이 실행될 경우를 대비한 필드 초기화
        return {
            "impact_groups": impact_groups, 
            "next_step": "retriever",
            "iterations": state.get("iterations", 0),
            "max_iterations": state.get("max_iterations", 3),
            "validation_results": state.get("validation_results", []),
            "scenarios": state.get("scenarios", []),
            "errors": state.get("errors", [])
        }

    def retriever_node(self, state: IntegrationState):
        """각 엔드포인트 그룹별 컨텍스트를 수집합니다."""
        logger.info("Retrieving contexts for impact groups...")
        contexts = {}
        
        for endpoint, group in state["impact_groups"].items():
            methods_context = []
            all_dtos = {}
            processed_signatures = set()
            
            # 엔드포인트 메서드 정보 식별
            public_dto_names = set()
            
            for path in group["paths"]:
                source_node = path.nodes[0]
                if "METHOD" in source_node.labels and source_node.get("signature") not in processed_signatures:
                    # 응답 DTO 추출 (ResponseEntity<T> 대응)
                    ret_type_obj = source_node.get("return_type")
                    ret_type = ret_type_obj.get("given") if isinstance(ret_type_obj, dict) else ret_type_obj
                    if ret_type and "ResponseEntity<" in ret_type:
                        try:
                            # ResponseEntity<LoginResDto> -> LoginResDto
                            actual_dto = ret_type.split('<')[1].split('>')[0]
                            public_dto_names.add(actual_dto)
                        except Exception:
                            public_dto_names.add(ret_type)
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
                                "returnType": node.get("return_type") # JSON object
                            })
                            processed_signatures.add(sig)
                            self._collect_dto_info(sig, all_dtos)
            
            # [추가] 변경된 원인 메서드들(trigger_methods)의 1-depth 하위 메서드 수집
            for m_id in group["source_methods"]:
                downstream_res = self.db_client.execute_query(
                    CypherQueries.GET_1_DEPTH_DOWNSTREAM_METHODS,
                    {"method_id": m_id}
                )
                for row in downstream_res:
                    sig = row["signature"]
                    # 이미 경로에 포함되어 있거나 처리된 경우 제외
                    if sig and sig not in processed_signatures:
                        methods_context.append({
                            "name": row["name"],
                            "signature": sig,
                            "source": row["source"],
                            "returnType": row["returnType"] # JSON from query alias
                        })
                        processed_signatures.add(sig)
                        self._collect_dto_info(sig, all_dtos)
            
            # DTO 분류 (Public vs Internal)
            public_dtos = {}
            internal_dtos = {}
            for t_name, fields in all_dtos.items():
                # 간단한 이름 매칭 (fullName 혹은 simpleName)
                is_public = any(p in t_name for p in public_dto_names)
                if is_public:
                    public_dtos[t_name] = fields
                else:
                    internal_dtos[t_name] = fields

            contexts[endpoint] = {
                "methods": methods_context,
                "public_dtos": public_dtos,
                "internal_dtos": internal_dtos,
                "trigger_methods": group["source_methods"],
                "trigger_method_names": group.get("source_method_names", []),
                "public_dto_names": list(public_dto_names)
            }
            
        return {"contexts": contexts, "next_step": "generator"}

    def generator_node(self, state: IntegrationState):
        """수집된 컨텍스트를 기반으로 추적성이 포함된 시나리오를 생성합니다."""
        logger.info("Generating traceability-aware scenarios...")
        scenarios = []
        errors = []
        
        for endpoint, context in state["contexts"].items():
            # 엔드포인트가 비어있거나 None인 경우 스킵
            if not endpoint or endpoint not in state["impact_groups"]:
                continue
                 
            group = state["impact_groups"][endpoint]
            
            # 원인 메서드 이름들을 가져와서 프롬프트에 포함 (추적성 확보)
            trigger_names = context.get('trigger_method_names', [])
            if not trigger_names:
                trigger_names = [m.split('.')[-1] for m in context['trigger_methods']] # fallback
            
            # 이전 피드백이 있는 경우 프롬프트에 추가
            feedback_str = ""
            if state.get("validation_results"):
                endpoint_feedback = [vr for vr in state["validation_results"] if vr.get("endpoint") == endpoint]
                if endpoint_feedback:
                    feedback_str = f"""
### ⚠️ 이전 검증 피드백 (반드시 반영 필요)
다음은 이전 시도에서 발견된 결함들입니다. 이번 생성 시에는 아래 피드백을 최우선으로 반영하여 결함을 보정해 주세요:
{endpoint_feedback[-1]['feedback']}
"""

            prompt = f"""
전략적인 통합 테스트 시나리오를 한국어로 생성해 주세요.
이 테스트는 특히 다음 변경된 메서드들의 영향도를 검증해야 합니다: {', '.join(trigger_names)}
{feedback_str}

[대상 엔드포인트]
- URL: {endpoint}
- Method: {group['http_method']}
- Name: {group['name']}

[비즈니스 로직 문맥 (영향 경로상의 코드)]
{json.dumps(context['methods'], indent=2, ensure_ascii=False)}

[Public API DTO 구조 (필수 준수)]
{json.dumps(context['public_dtos'], indent=2, ensure_ascii=False)}

[Internal Data structures (참고용 컨텍스트)]
{json.dumps(context['internal_dtos'], indent=2, ensure_ascii=False)}

[DTO 매핑 지침]
- **Request Payload**: `{', '.join(context['public_dto_names']) if context['public_dto_names'] else 'N/A'}` 구조 중 요청에 해당하는 것을 엄격히 따라야 합니다.
- **Response Payload**: `{', '.join(context['public_dto_names']) if context['public_dto_names'] else 'N/A'}` 구조 중 응답에 해당하는 것을 엄격히 따라야 합니다.
- **중요**: 최종 응답 바디에는 [Public API DTO] 구조만 사용하고, [Internal Data structures]에 있는 필드(예: token 등)를 바디에 섞지 마세요.

[추가 요구사항]
1. 모든 설명과 결과는 **한국어**로 작성해 주세요.
2. `scenario` 필드 ("의도"):
   - **반드시** 아래의 마크다운 형식을 엄격히 준수하여 작성해 주세요:
   
   ### 🎯 테스트 목적
   [이 테스트를 통해 검증하고자 하는 핵심 목적 서술]

   ### 🔍 변경 사항 및 영향도
   - **대상 메서드**: {', '.join(trigger_names)}
   - **영향 내용**: [변경된 로직이 해당 엔드포인트의 비즈니스 로직에 미치는 영향 설명]

   ### 💡 주요 검증 포인트
   - [ ] [검증 포인트 1]
   - [ ] [검증 포인트 2]
   - [ ] [예외 상황 검증 항목] (예외나 에러 타입 명칭은 반드시 **볼드체**로 표기해 주세요. 단순하게 'CustomException'이나 'Exception'이라고만 적지 말고, 포함된 구체적인 에러 코드나 메시지 등을 원본 코드에 명시된 그대로 작성해 주세요. 예: **IllegalArgumentException**, **CustomException(ErrorCode.USER_NOT_FOUND)**)

3. `expected_result` 필드 ("기대 결과 표"):
   - 이 필드는 반드시 **마크다운 표(Markdown Table)** 형식으로 작성해야 합니다.
   - 표 컬럼 예시: `| 구분 | 상태 코드 | 검증 항목 | 비고 |`
   - 성공 케이스와 다양한 실패 케이스(예외 상황)를 표에 모두 포함해 주세요. (예외 발생 시 해당 에러 타입은 **볼드체**로 작성하되, 포괄적인 예외 클래스명만 쓰지 말고 상세 에러 코드, 상태 등을 구체적으로 명시해 주세요)
4. `request` 객체:
   - `payload`: 엔드포인트로 전송할 샘플 Request JSON을 문자열로 작성해 주세요. **중요**: `[Public API DTO 구조]`에 정의된 모든 필드를 누락 없이 포함해야 합니다.
   - `headers`: **제공된 [비즈니스 로직 문맥] 코드에서 명시적으로 확인되는 헤더**만 작성해 주세요 (예: `@RequestHeader`, `HttpServletRequest.getHeader()` 등으로 추출되는 값).
   - **주의**: 단순 추측으로 `Authorization: Bearer ...`와 같은 인증 헤더를 추가하지 마세요. 특히 로그인(`/login`) 처럼 토큰을 **발급받기 전**인 경우 요청 헤더에 토큰이 있어서는 안 됩니다.
   - `Content-Type: application/json`과 같이 자명한 표준 헤더는 제외하세요.
5. `response` 객체:
   - `payload`: 성공 케이스에서 반환될 것으로 예상되는 샘플 Response JSON을 문자열로 작성해 주세요. **중요**: 해당 응답 DTO에 정의된 모든 필드를 실제 데이터 구조와 동일하게 포함해야 합니다.
   - `headers`: **[비즈니스 로직 문맥] 코드에서 명시적으로 조작되는 헤더**만 작성해 주세요 (예: `response.setHeader()`, `HttpHeaders.set()` 등). 
   - **주의**: 바디에 포함된 값을 습관적으로 헤더에 중복 포함하지 마세요.
"""
            try:
                result = self.structured_llm.invoke(prompt)
                
                # Request Payload JSON 파싱 시도
                request_payload_obj = {}
                try:
                    if not result.request.payload.strip():
                        request_payload_obj = {}
                    else:
                        request_payload_obj = json.loads(result.request.payload)
                except Exception:
                    logger.warning(f"Failed to parse request_payload for {endpoint}, using raw string.")
                    request_payload_obj = {"raw": result.request.payload}

                # Response Payload JSON 파싱 시도
                response_payload_obj = {}
                try:
                    if not result.response.payload.strip():
                        response_payload_obj = {}
                    else:
                        response_payload_obj = json.loads(result.response.payload)
                except Exception:
                    logger.warning(f"Failed to parse response_payload for {endpoint}, using raw string.")
                    response_payload_obj = {"raw": result.response.payload}

                scenarios.append({
                    "endpoint": endpoint,
                    "http_method": group['http_method'],
                    "trigger_methods": trigger_names,
                    "result": {
                        "scenario": result.scenario,
                        "expected_result": result.expected_result,
                        "request": {
                            "payload": request_payload_obj,
                            "headers": result.request.headers
                        },
                        "response": {
                            "payload": response_payload_obj,
                            "headers": result.response.headers
                        }
                    }
                })
            except Exception as e:
                logger.error(f"Generation failed for {endpoint}: {e}")
                errors.append(f"{endpoint}: {str(e)}")
                
        # 에러가 있으면 상태에 병합 (기존 errors 리스트에 추가됨)
        # 생성할 때마다 iteration 증가 (_build_graph에서 처리해도 되지만 여기서 명시적으로 기록할 수도 있음)
        return {"scenarios": scenarios, "errors": errors, "iterations": state["iterations"] + 1}

    def validator_node(self, state: IntegrationState):
        """생성된 시나리오의 논리적 결함 및 JSON 유효성을 검토합니다."""
        logger.info(f"Validating scenarios (Iteration: {state['iterations']}/ {state['max_iterations']})...")
        
        validation_results = []
        all_valid = True
        
        for scenario_data in state["scenarios"]:
            endpoint = scenario_data["endpoint"]
            context = state["contexts"].get(endpoint, {})
            trigger_names = context.get('trigger_method_names', [])
            if not trigger_names:
                trigger_names = [m.split('.')[-1] for m in context.get('trigger_methods', [])]
            
            prompt = f"""
다음 생성된 테스트 시나리오를 검토하고 피드백을 주세요.

[대상 엔드포인트]
- {endpoint} ({scenario_data['http_method']})

[코드 문맥]
{json.dumps(context.get('methods', []), indent=2, ensure_ascii=False)}

[Public API DTO 구조 (바디 검증 기준)]
{json.dumps(context.get('public_dtos', {}), indent=2, ensure_ascii=False)}

[Internal Data structures (참고용 컨텍스트)]
{json.dumps(context.get('internal_dtos', {}), indent=2, ensure_ascii=False)}

[변경된 메서드]
{', '.join(trigger_names)}

[검토 대상 시나리오]
{json.dumps(scenario_data['result'], indent=2, ensure_ascii=False)}

[DTO 매핑 정보]
- 이 엔드포인트의 **공개 API DTO**: `{', '.join(context.get('public_dto_names', []))}`
- 위 **공개 API DTO** 리스트에 정의된 필드**만** `request.payload`와 `response.payload`에 포함되어야 합니다.

[검증 기준]
1. **JSON 및 헤더 정합성 (최우선)**: 
   - `request.payload`와 `response.payload`가 각각의 **공개 API DTO** 구조 및 필드와 정확히 일치하는가?
   - **헤더 타당성**: `request.headers`에 포함된 헤더가 **제공된 [코드 문맥]에서 실제로 요구하거나 사용하는지** 확인하세요. 코드에 없는 `Authorization` 등의 헤더를 임의로 생성했다면 이는 결함입니다.
   - **헤더/바디 분리**: 소스 코드의 `HttpHeaders` 로직에 명시된 데이터가 바디(`payload`)가 아닌 헤더(`headers`)에 정확히 위치했는가?
   - **Internal DTO 혼입 금지**: `Internal Data structures`에만 정의된 필드가 본문(바디)에 섞여 들어가지 않았는가?
2. 논리적 일관성: 시나리오가 비즈니스 로직 및 HTTP 메서드에 부합하는가?
3. 추적성: 변경된 메서드({', '.join(trigger_names)})의 영향도가 잘 설명되었는가?
4. 형식 준수: 마크다운 서식 및 표 형식을 엄격히 따르는가?

결함이 있다면 **누락된 필드명이나 잘못된 구조를 상세히 기술**하여 `feedback`에 작성하고 `is_valid`를 false로 설정하세요. 모든 필드가 포함되고 기준을 통과하면 `is_valid`를 true로 설정하세요.
"""
            try:
                validation = self.validator_llm.invoke(prompt)
                validation_results.append({
                    "endpoint": endpoint,
                    "is_valid": validation.is_valid,
                    "feedback": validation.feedback
                })
                if not validation.is_valid:
                    all_valid = False
            except Exception as e:
                logger.error(f"Validation failed for {endpoint}: {e}")
                validation_results.append({
                    "endpoint": endpoint,
                    "is_valid": False,
                    "feedback": f"Validation process error: {str(e)}"
                })
                all_valid = False
        
        # 모든 시나리오가 유효하거나 최대 반복 횟수에 도달하면 종료로 보냄
        next_step = "generator"
        if all_valid or state["iterations"] >= state["max_iterations"]:
            next_step = END
            
        return {"validation_results": validation_results, "next_step": next_step}

    def _should_continue(self, state: IntegrationState):
        """루프를 계속할지 결정하는 조건부 로직입니다."""
        if state["next_step"] == END:
            return END
        return "generator"

    def _build_graph(self):
        workflow = StateGraph(IntegrationState)

        # 노드 추가
        workflow.add_node("planner", self.planner_node)
        workflow.add_node("retriever", self.retriever_node)
        workflow.add_node("generator", self.generator_node)
        workflow.add_node("validator", self.validator_node)

        # 엣지 정의 (흐름)
        workflow.set_entry_point("planner")
        workflow.add_edge("planner", "retriever")
        workflow.add_edge("retriever", "generator")
        workflow.add_edge("generator", "validator")
        
        # 조건부 엣지
        workflow.add_conditional_edges(
            "validator",
            self._should_continue,
            {
                "generator": "generator",
                END: END
            }
        )

        return workflow.compile()

    def run(self, source_method_ids: List[str], max_iterations: int = 3):
        """그래프를 실행합니다."""
        initial_state = {
            "source_method_ids": source_method_ids,
            "impact_groups": {},
            "contexts": {},
            "scenarios": [],
            "iterations": 0,
            "max_iterations": max_iterations,
            "validation_results": [],
            "errors": [],
            "next_step": ""
        }
        return self.graph.invoke(initial_state)

    def _collect_dto_info(self, method_signature, dtos_context):
        """메서드의 파라미터 및 리턴 타입과 연관된 DTO 필드 정보를 수집합니다."""
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
            # 파라미터 DTO 처리
            if row["pt_name"]:
                t_name = row["pt_name"]
                if t_name not in dtos_context:
                    dtos_context[t_name] = []
                if row["pf_name"] and not any(f["name"] == row["pf_name"] for f in dtos_context[t_name]):
                    # Check if pf_type is dict
                    p_f_type = row["pf_type"].get("given") if isinstance(row["pf_type"], dict) else row["pf_type"]
                    dtos_context[t_name].append({"name": row["pf_name"], "type": p_f_type})
            
            # 리턴 타입 DTO 처리 (Response)
            if row["rt_name"]:
                t_name = row["rt_name"]
                if t_name not in dtos_context:
                    dtos_context[t_name] = []
                if row["rf_name"] and not any(f["name"] == row["rf_name"] for f in dtos_context[t_name]):
                    # Check if rf_type is dict
                    r_f_type = row["rf_type"].get("given") if isinstance(row["rf_type"], dict) else row["rf_type"]
                    dtos_context[t_name].append({"name": row["rf_name"], "type": r_f_type})
