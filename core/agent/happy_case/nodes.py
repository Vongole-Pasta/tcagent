import logging
import json
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

from core.agent.happy_case.state import ImpactGroup, HappyCaseState, WorkerState, HappyCaseOutput
from core.agent.happy_case.query import HappyCaseQueries
from graph_db.client import DBClient
from graph_db.queries import CypherQueries
from core.agent.happy_case.prompts import GENERATOR_NODE_PROMPT

logger = logging.getLogger(__name__)

class HappyCaseAgentNodes:
    def __init__(self, db_client: DBClient):
        self.db_client = db_client
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
        self.structured_llm = self.llm.with_structured_output(HappyCaseOutput)

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
                        "endpoint_qualnames": [],"source_methods": []
                    }
                
                # DB에서 전달받은 최종 엔드포인트 메서드의 qualname만 바로 사용합니다.
                # DB 단에서부터 불필요한 중간 경로를 생략하여 네트워크 및 메모리 낭비를 줄입니다.
                endpoint_qualname = row.get("qualname")
                
                # 이미 추가된 qualname은 건너뛰어 같은 메서드가 여러 경로로 발견돼도 중복 등록하지 않습니다.
                if endpoint_qualname and endpoint_qualname not in impact_groups[group_key]["endpoint_qualnames"]:
                    impact_groups[group_key]["endpoint_qualnames"].append(endpoint_qualname)
                
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
        DB에서 엔드포인트 메서드 및 관련 DTO 컨텍스트를 수집합니다.
        각 워커 세션 내에서 한 일만 실행되어 필요한 정보를 조회합니다.
        """
        group = state["group"]
        methods_context = []
        request_dtos = {}
        response_dtos = {}

        for qual in group["endpoint_qualnames"]:

            method_res = self.db_client.execute_query(
                "MATCH (m:METHOD {qualname: $qualname}) RETURN m",
                {"qualname": qual}
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
                "source": method_node.get("source"),
                "params": params_info,
                "returnType": method_node.get("return_type")
            })
            # _collect_dto_info를 통해 파라미터/반환 타입 및 중첩 DTO들의 필드 구조를 수집합니다.
            self._collect_dto_info(qual, request_dtos, response_dtos)

        return {
            "context": {
                "methods": methods_context, 
                "dto_context": {
                    "request": request_dtos,
                    "response": response_dtos
                }
            }
        }

    def generator_worker_node(self, state: WorkerState):
        """
        수집된 컨텍스트로 LLM을 호출하여 시나리오를 생성합니다.
        """
        group = state["group"]
        endpoint_url = group["url"]
        context = state.get("context", {})


        prompt_template = PromptTemplate.from_template(GENERATOR_NODE_PROMPT)
        prompt = prompt_template.format(
            endpoint_url=endpoint_url,
            http_method=group['http_method'],
            name=group['name'],
            methods_context=json.dumps(context.get('methods', []), indent=2, ensure_ascii=False),
            dto_context=json.dumps(context.get('dto_context', {}), indent=2, ensure_ascii=False)
        )

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

    def _collect_dto_info(self, method_qualname, request_dtos, response_dtos):
        """
        특정 메서드의 파라미터(Request) 및 반환 타입(Response) 중첩 DTO의 필드 구조를 분리하여 수집합니다.
        Cypher 홉(Hop) 수 10은 'TYPE-FIELD-TYPE' 구조를 고려할 때 최대 5단계의 중첩을 의미합니다.
        """
        # Request DTO 조회
        req_results = self.db_client.execute_query(HappyCaseQueries.RETRIEVER_NODE_GET_REQUEST_DTO_STRUCTURE, {"qualname": method_qualname})
        self._populate_dtos(req_results, request_dtos)

        # Response DTO 조회
        res_results = self.db_client.execute_query(HappyCaseQueries.RETRIEVER_NODE_GET_RESPONSE_DTO_STRUCTURE, {"qualname": method_qualname})
        self._populate_dtos(res_results, response_dtos)

    def _populate_dtos(self, results, dtos_context):
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
