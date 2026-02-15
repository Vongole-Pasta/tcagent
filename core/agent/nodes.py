
import logging
import json
import re
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser

from config import Config
from infra.db_client import DBClient
from core.agent.state import AgentState, TargetMethod, TraceResult, GeneratedScenario, ValidationTarget
from core.agent.prompts import SCENARIO_GENERATION_PROMPT, TEST_STRATEGY_PROMPT, SCENARIO_EVALUATION_PROMPT

logger = logging.getLogger(__name__)

class IntegratedTestAgentNodes:
    def __init__(self, db_client: DBClient):
        self.db_client = db_client
        self.llm = ChatOpenAI(
            model=Config.MODEL_NAME,
            temperature=0,
            api_key=Config.OPENAI_API_KEY
        )

    def _parse_json_safely(self, text: str) -> Any:
        # 1. 직접 파싱 시도
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
            
        # 2. 마크다운 코드 블록에서 JSON 추출 (선택적 "json" 태그 처리)
        # 백틱 사이의 모든 내용을 캡처하는, 더 관대한 정규식 사용
        match = re.search(r"```(json)?(.*?)```", text, re.DOTALL)
        if match:
            clean_text = match.group(2).strip()
            try:
                return json.loads(clean_text)
            except json.JSONDecodeError:
                pass # 백틱 내부 내용이 유효한 JSON이 아닌 경우 통과
 
        # 3. 대체 방법: 첫 번째 '[' 또는 '{'와 마지막 ']' 또는 '}' 찾기
        # 백틱이 없거나 잘못된 형식인 경우를 처리
        try:
            # 리스트 또는 객체 찾기
            list_start = text.find('[')
            list_end = text.rfind(']')
            obj_start = text.find('{')
            obj_end = text.rfind('}')
            
            start = -1
            end = -1
            
            # 리스트인지 객체인지 판단하고 먼저 나오는 것을 선택
            if list_start != -1 and (obj_start == -1 or list_start < obj_start):
                start = list_start
                end = list_end
            elif obj_start != -1:
                start = obj_start
                end = obj_end
                
            if start != -1 and end != -1 and end > start:
                json_candidate = text[start:end+1]
                return json.loads(json_candidate)
        except json.JSONDecodeError:
            pass
            
        raise ValueError(f"Failed to parse JSON from text: {text[:100]}...")


    def identify_targets(self, state: AgentState) -> Dict[str, Any]:
        """
        수정되었거나 새로운 메서드를 식별합니다.
        """
        logger.info("대상 메서드(NEW/MODIFIED) 식별 중...")
        query = """
        MATCH (m:METHOD)
        WHERE m.status IN ['NEW', 'MODIFIED']
        RETURN elementId(m) as id, m.name as name, m.signature as signature, m.status as status
        """
        results = self.db_client.execute_query(query)
        
        targets = []
        for row in results:
            targets.append(TargetMethod(
                id=row['id'],
                name=row['name'],
                signature=row['signature'],
                status=row['status']
            ))
            
        logger.info(f"{len(targets)}개의 대상 메서드를 발견했습니다.")
        return {"target_methods": targets}

    def trace_roots(self, state: AgentState) -> Dict[str, Any]:
        """
        대상 메서드를 호출하는 루트 메서드(진입점)까지 역추적합니다.
        컨텍스트 보강을 위해 중간 노드들도 수집합니다.
        """
        targets = state.target_methods
        trace_results = []
        
        logger.info(f"{len(targets)}개 대상에 대한 루트 추적 중...")
        
        # root_method_id별로 트레이스를 그룹화하기 위한 딕셔너리
        # Key: root_method_id, Value: TraceResult
        grouped_traces: Dict[str, TraceResult] = {}
        
        try:
            for target in targets:
                # 루트 메서드(프로젝트 컨텍스트 내에서 다른 메서드에 의해 호출되지 않는 메서드)를 찾습니다.
                # 또는 명시적인 컨트롤러 엔드포인트인 메서드를 찾습니다.
                # 단순화를 위해 가장 긴 상위 경로를 찾습니다.
                # 'nodes(path)'를 반환하도록 업데이트됨
                query = """
                MATCH path = (root:METHOD)-[:CALLS*0..]->(target:METHOD)
                WHERE (elementId(target) = $target_id)
                  AND NOT ()-[:CALLS]->(root)
                RETURN root, target, nodes(path) as path_nodes
                LIMIT 5
                """
                
                paths = self.db_client.execute_query(query, {"target_id": target.id})
                
                for row in paths:
                    root_node = row['root']
                    target_node = row['target']
                    path_nodes = row['path_nodes'] # Neo4j 노드 리스트
                    
                    root_id = root_node.element_id
                    
                    # 중간 노드 추출 (루트[0]와 타겟[-1] 제외)
                    # 최적화: 중간 경로의 소스 코드는 더 이상 프롬프트에 사용되지 않으므로 추출하지 않음 (메모리/DB 부하 감소)
                    intermediates = []
                    if len(path_nodes) > 2:
                        for node in path_nodes[1:-1]:
                            intermediates.append({
                                "id": node.element_id,
                                "signature": node.get('signature', 'unknown'),
                                "code": "" # 불필요한 소스 코드 데이터 제거
                            })

                    # ValidationTarget 객체 생성
                    # 최적화: 루트 메서드와 동일한 경우 코드를 중복 저장하지 않음 (토큰 절약)
                    is_root_duplicate = (target_node.element_id == root_id)
                    
                    validation_target = {
                        "id": target_node.element_id,
                        "signature": target_node.get('signature', ''),
                        "code": "" if is_root_duplicate else target_node.get('source', ''),
                        "path_trace": intermediates # 서명 정보만 포함된 경량화된 리스트
                    }

                    if root_id in grouped_traces:
                        # 고유한 경우 기존 트레이스에 추가
                        existing = grouped_traces[root_id]
                        if not any(vt.id == validation_target['id'] for vt in existing.validation_targets):
                            existing.validation_targets.append(ValidationTarget(**validation_target))
                    else:
                        # 루트 메서드 컨텍스트를 위한 파라미터 조회 (루트당 한 번만)
                        # 업데이트된 쿼리: 어노테이션 및 DTO 필드 조회
                        param_query = """
                        MATCH (m:METHOD)-[:CONTAINS]->(p:PARAMETER)
                        WHERE elementId(m) = $root_id
                        OPTIONAL MATCH (p)-[:OF_TYPE]->(t:TYPE)
                        OPTIONAL MATCH (t)-[:CONTAINS]->(f:FIELD)
                        RETURN p.index as param_index, 
                               p.name as param_name, 
                               p.type as param_type, 
                               collect({name: f.name, type: f.type}) as fields
                        ORDER BY param_index
                        """
                        params_result = self.db_client.execute_query(param_query, {"root_id": root_id})
                        
                        parameter_infos = []
                        for p_row in params_result:
                            # 현재는 간단한 스키마 구성 (재귀적 조회는 비용이 큼)
                            # 'fields'가 DTO 구조를 나타낸다고 가정
                            raw_fields = p_row['fields']
                            clean_fields = {}
                            for f in raw_fields:
                                if f.get('name') and f.get('type'):
                                    clean_fields[f['name']] = f['type']
                            
                            parameter_infos.append({
                                "name": p_row['param_name'],
                                "type": p_row['param_type'],
                                "dto_schema": clean_fields if clean_fields else None
                            })


                        root_method_code = root_node.get('source', '')
                        root_method_signature = root_node.get('signature', '')

                        grouped_traces[root_id] = TraceResult(
                            root_method_id=root_id,
                            root_method_signature=root_method_signature,
                            root_method_code=root_method_code,
                            validation_targets=[ValidationTarget(**validation_target)],
                            parameters=parameter_infos
                        )

        except Exception as e:
            import traceback
            logger.error(f"trace_roots 중 치명적 오류 발생: {e}")
            traceback.print_exc()
            raise e

        trace_results = list(grouped_traces.values())
        logger.info(f"여러 대상을 포괄하는 {len(trace_results)}개의 고유 루트 경로를 추적했습니다.")
        return {"trace_results": trace_results}


    def generate_scenarios(self, state: AgentState) -> Dict[str, Any]:
        """
        그룹화된 트레이스 결과를 기반으로 LLM을 사용하여 테스트 시나리오를 생성합니다.
        가능한 경우 원본 코드 대신 요약된 컨텍스트를 사용합니다.
        Critic 에이전트의 피드백 루프를 처리합니다.
        """
        traces = state.trace_results
        all_generated_scenarios = []
        
        logger.info(f"{len(traces)}개 루트 그룹에 대한 시나리오 생성 중...")
        
        chain = SCENARIO_GENERATION_PROMPT | self.llm | StrOutputParser()
        
        for i, trace in enumerate(traces):
            # 이미 평가를 통과한 경우 건너뜀
            if trace.evaluation_passed:
                all_generated_scenarios.extend(trace.generated_scenarios)
                continue
            
            # 재시도 제한에 도달한 경우 건너뜀 (이전 결과 수용)
            if trace.retry_count >= 2 and trace.generated_scenarios:
                logger.warning(f"트레이스 {i} 재시도 제한 도달. 현재 시나리오 수용.")
                trace.evaluation_passed = True
                all_generated_scenarios.extend(trace.generated_scenarios)
                continue

            try:
                validation_context = ""
                for idx, vt in enumerate(trace.validation_targets):
                    # 코드 가져오기 (최적화된 경우 루트 코드 사용)
                    vt_code = vt.code
                    if not vt_code and vt.id == trace.root_method_id:
                        vt_code = f"(Root Method Code와 동일)\n{trace.root_method_code[:2000]}"
                    elif not vt_code:
                        vt_code = "(코드 없음)"
                    else:
                        vt_code = vt_code[:2000]

                    validation_context += f"""
--- Target Method {idx+1} ---
Signature: {vt.signature}
Target Code:
{vt_code}...
"""
                
                # 루트 메서드 포맷팅 (가능한 경우 요약 + 부분 코드 사용)
                root_context = ""
                root_context += f"Signature: {trace.root_method_signature}\n"
                root_context += f"Code:\n{trace.root_method_code[:1000]}..."

                # LLM 입력 준비 (최적화: None 값 제외 및 불필요 메타데이터 제거)
                
                # 1. 파라미터 최적화
                params_json = json.dumps([p.model_dump(exclude_none=True) for p in trace.parameters], indent=2, ensure_ascii=False)
                
                # 2. 이전 시나리오 요약 (재시도 시 전체 덤프 대신 핵심 필드만 전달)
                previous_scenarios_json = "None"
                if trace.generated_scenarios:
                    summary_list = []
                    for s in trace.generated_scenarios:
                        summary_list.append({
                            "test_case_name": s.test_case_name,
                            "description": s.description,
                            "procedure": s.procedure,
                            "expected_result": s.expected_result
                            # 제외: test_case_id, step_no, scenario_id, root_method_signature (토큰 절약)
                        })
                    previous_scenarios_json = json.dumps(summary_list, indent=2, ensure_ascii=False)

                inputs = {
                    "root_method": root_context,
                    "validation_context": validation_context,
                    "parameters": params_json,
                    "feedback": trace.feedback if trace.feedback else "None",
                    "previous_scenarios": previous_scenarios_json
                }
                
                result_text = chain.invoke(inputs)
                
                try:
                    result = self._parse_json_safely(result_text)
                except Exception as e:
                    logger.error(f"트레이스 {i} 시나리오 파싱 실패: {e}")
                    raise e
                
                # 결과를 GeneratedScenario 객체로 파싱
                current_scenarios = []
                if isinstance(result, list):
                    for item in result:
                        scenario = GeneratedScenario(
                            test_case_id=f"TC-{len(all_generated_scenarios)+1:03d}",
                            test_case_name=item.get('test_case_name', 'No Name'),
                            step_no=item.get('step_no', 1),
                            description=item.get('description', ''),
                            pre_condition=item.get('pre_condition', ''),
                            procedure=item.get('procedure', ''),
                            expected_result=item.get('expected_result', ''),
                            scenario_id=f"SC-{i+1:03d}",
                            root_method_signature=trace.root_method_signature
                        )
                        current_scenarios.append(scenario)
                
                # Update Trace Result
                trace.generated_scenarios = current_scenarios
                all_generated_scenarios.extend(current_scenarios)
                logger.info(f"루트 그룹 {i+1}에 대해 {len(current_scenarios)}개의 시나리오 생성됨")
                
            except Exception as e:
                logger.error(f"트레이스 {i} 시나리오 생성 실패: {e}")
                # 이전 결과가 있으면 유지
                if trace.generated_scenarios:
                    all_generated_scenarios.extend(trace.generated_scenarios)
                    
        return {"generated_scenarios": all_generated_scenarios, "trace_results": traces}

    def evaluate_scenarios(self, state: AgentState) -> Dict[str, Any]:
        """
        Critic 노드: 생성된 시나리오를 평가하고 피드백을 제공합니다.
        """
        traces = state.trace_results
        logger.info("시나리오 평가 중 (Critic 모드)...")
        
        chain = SCENARIO_EVALUATION_PROMPT | self.llm | StrOutputParser()
        
        has_failure = False
        
        for i, trace in enumerate(traces):
            if trace.evaluation_passed:
                continue
                
            if not trace.generated_scenarios:
                continue

            # 재시도 제한 도달 시 건너뜀
            if trace.retry_count >= 2:
                trace.evaluation_passed = True
                continue

            try:
                # Critic을 위한 컨텍스트 준비
                validation_context = ""
                for vt in trace.validation_targets:
                    validation_context += f"Signature: {vt.signature}\nCode:\n{vt.code[:1000]}\n"
                
                scenarios_text = json.dumps([s.model_dump() for s in trace.generated_scenarios], indent=2, ensure_ascii=False)
                
                result_text = chain.invoke({
                    "validation_context": validation_context,
                    "scenarios": scenarios_text
                })
                
                try:
                    result = self._parse_json_safely(result_text)
                except Exception as e:
                    logger.error(f"트레이스 {i} 평가 파싱 실패: {e}")
                    raise e
                
                # 리스트 형태로 반환된 경우 처리 (여러 시나리오에 대한 개별 평가일 수 있음)
                if isinstance(result, list):
                    # 가장 보수적인 평가(최저 점수/FAIL)를 채택
                    final_decision = "PASS"
                    min_score = 100
                    feedbacks = []
                    
                    for item in result:
                        if isinstance(item, dict):
                            d = item.get("decision", "PASS")
                            s = item.get("score", 100)
                            f = item.get("feedback", "")
                            
                            if d == "FAIL":
                                final_decision = "FAIL"
                            if s < min_score:
                                min_score = s
                            if f:
                                feedbacks.append(f)
                    
                    decision = final_decision
                    score = min_score
                    feedback = "\n".join(feedbacks)
                else:
                    decision = result.get("decision", "PASS")
                    score = result.get("score", 100)
                    feedback = result.get("feedback", "")
                
                if decision == "FAIL" or score < 80:
                    logger.warning(f"트레이스 {i} 평가 실패. 점수: {score}. 피드백: {feedback}")
                    trace.evaluation_passed = False
                    trace.feedback = feedback
                    trace.retry_count += 1
                    has_failure = True
                else:
                    logger.info(f"트레이스 {i} 평가 통과. 점수: {score}.")
                    trace.evaluation_passed = True
                    trace.feedback = None
            
            except Exception as e:
                logger.error(f"트레이스 {i} 평가 실패: {e}")
                # Critic 실패 시 통과로 가정
                trace.evaluation_passed = True

        return {"trace_results": traces} # 피드백 상태 반영을 위한 업데이트

    def synthesize_strategy(self, state: AgentState) -> Dict[str, Any]:
        """
        식별된 대상 및 루트를 기반으로 테스트 전략 요약을 생성합니다.
        """
        targets = state.target_methods
        traces = state.trace_results
        
        logger.info(f"{len(targets)}개 대상 및 {len(traces)}개 루트에 대한 전략 합성 중...")
        
        # 1. 대상 요약
        target_summary = ""
        for t in targets:
            target_summary += f"- [{t.status}] {t.name} ({t.signature})\n"
        
        # 2. 루트 요약
        trace_summary = ""
        for tr in traces:
            entry_point = tr.root_method_signature
            trace_summary += f"- Entry Point: {entry_point}\n"
            trace_summary += f"  - Validation Targets: {len(tr.validation_targets)} methods\n"
        
        if not targets:
            return {"test_strategy_summary": "변경된 사항이 감지되지 않았습니다."}

        # 3. LLM 호출
        chain = TEST_STRATEGY_PROMPT | self.llm | StrOutputParser()
        
        inputs = {
            "target_summary": target_summary,
            "trace_summary": trace_summary
        }
        
        try:
            strategy_text = chain.invoke(inputs)
            logger.info("전략 합성 성공.")
            return {"test_strategy_summary": strategy_text}
        except Exception as e:
            logger.error(f"전략 합성 실패: {e}")
            return {"test_strategy_summary": f"전략 수립 중 오류 발생: {e}"}
