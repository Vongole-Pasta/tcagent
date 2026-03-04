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
    
    impact_groups: NotRequired[Dict[str, ImpactGroup]] # 분석 결과: 식별된 엔드포인트 그룹 (key: "HTTP_METHOD:URL")
    # Annotated[..., operator.add]: 병렬 워커들이 각자 반환하는 리스트를 덮어쓰지 않고 자동으로 누적(append)합니다.
    worker_results: Annotated[NotRequired[List[Dict[str, Any]]], operator.add] # 각 워커의 중간 결과물 (검증 통과 후 집계)
    scenarios: NotRequired[List[Dict[str, Any]]]       # 최종 결과물 (TC-001 등 ID 부여 완료)
    # errors도 리듀서 적용: 여러 워커에서 발생한 에러를 하나의 리스트로 합칩니다.
    errors: Annotated[NotRequired[List[str]], operator.add]

class WorkerState(TypedDict):
    """
    개별 엔드포인트 작업을 위한 State입니다.
    retriever -> generator -> validator 순서로 데이터가 전달됩니다.
    """
    endpoint_url: str
    group: ImpactGroup
    context: NotRequired[Dict[str, Any]]         # retriever가 수집한 메서드/DTO 컨텍스트
    scenario: NotRequired[Dict[str, Any]]        # generator가 생성한 시나리오
    retry_count: NotRequired[int]                # 자가 교정 재시도 횟수
    retry_errors: NotRequired[List[str]]         # generator에게 전달할 이전 실패 사유
    worker_results: Annotated[NotRequired[List[Dict[str, Any]]], operator.add]  # 검증 통과된 최종 결과

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
                
                # Path 객체의 모든 노드 중 METHOD 레이블을 가진 노드의 시그니처만 추출합니다.
                # Path 자체(neo4j Path 객체)를 State에 저장하면 직렬화 비용이 높아지므로,
                # 필요한 식별자(signature 문자열)만 분리하여 경량화합니다.
                path_signatures = [node.get("signature") for node in row["path"].nodes if "METHOD" in node.labels]
                
                # 이미 추가된 시그니처는 건너뛰어 같은 메서드가 여러 경로로 발견돼도 중복 등록하지 않습니다.
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

    def retriever_worker_node(self, state: WorkerState):
        """
        DB에서 메서드/DTO 컨텍스트를 수집합니다.
        루프가 발생하더라도 이 노드는 재실행되지 않아 중복 DB 조회를 방지합니다.
        """
        group = state["group"]
        methods_context = []
        all_dtos = {}
        processed_signatures = set()
        public_dto_names = set()

        for sig in group["related_signatures"]:
            if sig in processed_signatures: continue

            method_res = self.db_client.execute_query(
                "MATCH (m:METHOD {signature: $signature}) RETURN m",
                {"signature": sig}
            )
            if not method_res: continue
            method_node = method_res[0]["m"]

            # 반환 타입이 ResponseEntity<DTO> 형태면 제네릭 파라미터(DTO 이름)가 실제 응답 DTO입니다.
            # 그 외의 비-void 타입도 직접 반환 DTO로 간주합니다.
            ret_type_obj = method_node.get("return_type")
            ret_type = ret_type_obj.get("given") if isinstance(ret_type_obj, dict) else ret_type_obj
            if ret_type and "ResponseEntity<" in ret_type:
                try: actual_dto = ret_type.split('<')[1].split('>')[0]; public_dto_names.add(actual_dto)
                except: pass
            elif ret_type and ret_type != "void":
                public_dto_names.add(ret_type)

            # 메서드의 첫 번째 파라미터 타입을 요청 DTO로 추론합니다 (LIMIT 1).
            param_query = "MATCH (m:METHOD {signature: $signature})-[:HAS_PARAMETER]->(t:TYPE) RETURN t.fullName as type_name LIMIT 1"
            param_res = self.db_client.execute_query(param_query, {"signature": sig})
            if param_res: public_dto_names.add(param_res[0]["type_name"])

            methods_context.append({
                "name": method_node.get("name"),
                "signature": sig,
                "source": method_node.get("source"),
                "returnType": method_node.get("return_type")
            })
            processed_signatures.add(sig)
            # _collect_dto_info를 통해 파라미터/반환 타입의 필드 구조를 수집합니다.
            self._collect_dto_info(sig, all_dtos)

        # public_dto_names에 추론된 DTO 이름이 포함된 타입은 Public(API 응답/요청 스펙)으로,
        # 그 외는 Internal(내부 도메인 객체)로 분류합니다.
        # validator는 Public DTO 스펙만을 기준으로 expected_result를 검증합니다.
        public_dtos = {}
        internal_dtos = {}
        for t_name, fields in all_dtos.items():
            if any(p in t_name for p in public_dto_names): public_dtos[t_name] = fields
            else: internal_dtos[t_name] = fields

        return {
            "context": {"methods": methods_context, "public_dtos": public_dtos, "internal_dtos": internal_dtos},
            "retry_count": 0,
            "retry_errors": []
        }

    def generator_worker_node(self, state: WorkerState):
        """
        수집된 컨텍스트로 LLM을 호출하여 시나리오를 생성합니다.
        이전 검증 실패 사유가 있으면 프롬프트에 포함하여 스스로 수정하도록 유도합니다.
        """
        endpoint_url = state["endpoint_url"]
        group = state["group"]
        context = state["context"]
        retry_errors = state.get("retry_errors", [])

        error_section = ""
        if retry_errors:
            error_section = f"""
        [이전 생성 실패 사유 - 반드시 수정 후 재생성]
        {chr(10).join(f'- {e}' for e in retry_errors)}
        """

        prompt = f"""
        당신은 백엔드 개발자이자 QA 엔지니어입니다. 제공된 코드 문맥을 분석하여 해당 API의 **Happy Case (성공 케이스, 200 OK)** 테스트 데이터를 생성해 주세요.
        {error_section}

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
            return {"scenario": scenario}
        except Exception as e:
            logger.error(f"LLM generation failed for {endpoint_url}: {e}")
            return {
                "retry_errors": [f"LLM 호출 오류: {str(e)}"],
                "retry_count": state.get("retry_count", 0) + 1
            }

    def validator_worker_node(self, state: WorkerState):
        """
        생성된 시나리오의 유효성을 검증합니다.
        검증 항목:
          1. input_data / expected_result가 유효한 JSON인지
          2. Public DTO에 정의된 필드 키가 expected_result에 모두 포함되어 있는지
          3. expected_result에 DTO에 없는 불필요한 키가 섞여 있지 않은지
        """
        endpoint_url = state.get("endpoint_url")
        scenario = state.get("scenario")
        context = state.get("context", {})
        retry_count = state.get("retry_count", 0)

        if not scenario:
            return {
                "retry_errors": ["시나리오가 생성되지 않았습니다."],
                "retry_count": retry_count + 1
            }

        errors = []

        # --- 검증 1: JSON 형식 유효성 ---
        input_json = None
        result_json = None
        try:
            input_json = json.loads(scenario.get("input_data", "{}"))
        except Exception as e:
            errors.append(f"input_data가 유효한 JSON이 아닙니다: {e}")

        result_str = scenario.get("expected_result", "{}")
        # generator는 비즈니스 헤더(Location, Set-Cookie 등)를 "Header: Key=Value" 형식으로
        # JSON 바디 앞에 붙여 반환할 수 있습니다. JSON 파싱 전에 해당 라인을 제거합니다.
        json_part = result_str
        for line in result_str.splitlines():
            if line.strip().startswith("{") or line.strip().startswith("["):
                json_part = "\n".join(
                    l for l in result_str.splitlines()
                    if not l.strip().startswith("Header:")
                )
                break
        try:
            result_json = json.loads(json_part)
        except Exception as e:
            errors.append(f"expected_result가 유효한 JSON이 아닙니다: {e}")

        # --- 검증 2 & 3: DTO 키 일치 여부 ---
        public_dtos = context.get("public_dtos", {})
        if result_json and public_dtos and isinstance(result_json, dict):
            # expected_result가 단일 객체인 경우 (리스트의 경우 첫 번째 원소)
            result_obj = result_json
        elif result_json and public_dtos and isinstance(result_json, list) and result_json:
            result_obj = result_json[0] if isinstance(result_json[0], dict) else None
        else:
            result_obj = None

        if result_obj is not None and public_dtos:
            # 여러 Public DTO 중 어떤 것이 이 응답에 해당하는지 명시적으로 알 수 없으므로,
            # expected_result의 키와 가장 많이 겹치는 DTO를 "응답 DTO"로 자동 추론합니다.
            best_match_dto = None
            best_match_score = -1
            for dto_name, dto_fields in public_dtos.items():
                defined_keys = {f["name"] for f in dto_fields}
                result_keys = set(result_obj.keys())
                overlap = len(defined_keys & result_keys)
                if overlap > best_match_score:
                    best_match_score = overlap
                    best_match_dto = (dto_name, defined_keys)

            if best_match_dto and best_match_score >= 0:
                dto_name, defined_keys = best_match_dto
                result_keys = set(result_obj.keys())

                # 검증 2: DTO에 정의된 필수 키가 모두 있는지
                missing_keys = defined_keys - result_keys
                if missing_keys:
                    errors.append(f"expected_result에 DTO '{dto_name}'의 필드가 누락됐습니다: {missing_keys}")

                # 검증 3: DTO에 없는 불필요한 키가 섞여 있지 않은지
                extra_keys = result_keys - defined_keys
                if extra_keys:
                    errors.append(f"expected_result에 DTO '{dto_name}'에 정의되지 않은 필드가 있습니다: {extra_keys}")

        if errors:
            logger.warning(f"Validation failed for {endpoint_url} (attempt {retry_count}): {errors}")
            return {
                "retry_errors": errors,
                "retry_count": retry_count + 1
            }

        logger.info(f"Validation passed for {endpoint_url}")
        return {"worker_results": [scenario]}


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
        MAX_RETRIES = 3

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

        # --- 서브 그래프: 단일 엔드포인트 처리 (retriever -> generator <-> validator 루프) ---
        def worker_router(state: WorkerState):
            """검증 실패 시 재시도, 성공 또는 최대 재시도 초과 시 종료."""
            # retry_errors가 있으면 validator가 실패를 판정한 것입니다.
            # retry_count < MAX_RETRIES 인 경우에만 generator로 돌아가 재시도합니다.
            # MAX_RETRIES 이상이면 포기하고 worker_results 없이 END(빈 결과)로 종료합니다.
            if state.get("retry_errors") and state.get("retry_count", 0) < MAX_RETRIES:
                logger.warning(
                    f"Retrying generator for {state.get('endpoint_url')} "
                    f"(attempt {state.get('retry_count')}): {state.get('retry_errors')}"
                )
                return "generator"
            if state.get("retry_count", 0) >= MAX_RETRIES:
                logger.error(f"Max retries reached for {state.get('endpoint_url')}, giving up.")
            return END

        worker_builder = StateGraph(WorkerState)
        worker_builder.add_node("retriever", self.retriever_worker_node)
        worker_builder.add_node("generator", self.generator_worker_node)
        worker_builder.add_node("validator", self.validator_worker_node)

        worker_builder.set_entry_point("retriever")
        worker_builder.add_edge("retriever", "generator")
        worker_builder.add_edge("generator", "validator")
        worker_builder.add_conditional_edges("validator", worker_router, {"generator": "generator", END: END})

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
        특정 메서드의 파라미터 타입(요청 DTO)과 반환 타입(응답 DTO)의 필드 구조를 수집합니다.
        결과는 dtos_context 딕셔너리에 {타입명: [{name, type}, ...]} 형태로 누적됩니다.
        중복 필드는 any() 체크로 걸러냅니다.
        """
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
                    # TypeInfo 객체(dict)인 경우 "given" 키에서 실제 타입 문자열을 꺼냅니다.
                    p_f_type = row["pf_type"].get("given") if isinstance(row["pf_type"], dict) else row["pf_type"]
                    dtos_context[t_name].append({"name": row["pf_name"], "type": p_f_type})
            if row["rt_name"]:
                t_name = row["rt_name"]
                if t_name not in dtos_context: dtos_context[t_name] = []
                if row["rf_name"] and not any(f["name"] == row["rf_name"] for f in dtos_context[t_name]):
                    # TypeInfo 객체(dict)인 경우 "given" 키에서 실제 타입 문자열을 꺼냅니다.
                    r_f_type = row["rf_type"].get("given") if isinstance(row["rf_type"], dict) else row["rf_type"]
                    dtos_context[t_name].append({"name": row["rf_name"], "type": r_f_type})
