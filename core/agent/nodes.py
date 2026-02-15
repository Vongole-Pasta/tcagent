
import logging
import json
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser

from config import Config
from infra.db_client import DBClient
from core.agent.state import AgentState, TargetMethod, TraceResult, GeneratedScenario
from core.agent.prompts import SCENARIO_GENERATION_PROMPT, TEST_STRATEGY_PROMPT, SUMMARIZATION_PROMPT, SCENARIO_EVALUATION_PROMPT

logger = logging.getLogger(__name__)

class IntegratedTestAgentNodes:
    def __init__(self, db_client: DBClient):
        self.db_client = db_client
        self.llm = ChatOpenAI(
            model=Config.MODEL_NAME,
            temperature=0,
            api_key=Config.OPENAI_API_KEY
        )

    def identify_targets(self, state: AgentState) -> Dict[str, Any]:
        """
        수정되었거나 새로운 메서드를 식별합니다.
        """
        logger.info("대상 메서드(NEW/MODIFIED) 식별 중...")
        query = """
        MATCH (m:METHOD)
        WHERE m.status IN ['NEW', 'MODIFIED']
        OPTIONAL MATCH (m)<-[:CONTAINS]-(c:TYPE)<-[:CONTAINS]-(f:FILE)
        RETURN elementId(m) as id, m.name as name, m.signature as signature, m.status as status, f.path as file_path
        """
        results = self.db_client.execute_query(query)
        
        targets = []
        for row in results:
            targets.append(TargetMethod(
                id=row['id'],
                name=row['name'],
                signature=row['signature'],
                status=row['status'],
                file_path=row.get('file_path', 'UNKNOWN')
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
                path_nodes = row['path_nodes'] # List of Neo4j Nodes
                
                root_id = root_node.element_id
                
                # 중간 노드 추출 (루트[0]와 타겟[-1] 제외)
                intermediates = []
                if len(path_nodes) > 2:
                    for node in path_nodes[1:-1]:
                        intermediates.append({
                            "id": node.element_id,
                            "signature": node.get('signature', 'unknown'),
                            "code": node.get('source', '')
                        })

                # AffectedMethod 객체 생성
                affected_method = {
                    "id": target_node.element_id,
                    "signature": target_node.get('signature', ''),
                    "code": target_node.get('source', ''),
                    "call_path": [n.get('signature', '') for n in path_nodes], # For reference
                    "path_trace": intermediates # Populated with dicts, will be converted to MethodInfo
                }

                if root_id in grouped_traces:
                    # 고유한 경우 기존 트레이스에 추가
                    existing = grouped_traces[root_id]
                    if not any(am['id'] == affected_method['id'] for am in existing.affected_methods):
                        existing.affected_methods.append(affected_method)
                else:
                    # 루트 메서드 컨텍스트를 위한 파라미터 조회 (루트당 한 번만)
                    # 업데이트된 쿼리: 어노테이션 및 DTO 필드 조회
                    param_query = """
                    MATCH (m:METHOD)-[:CONTAINS]->(p:PARAMETER)
                    WHERE elementId(m) = $root_id
                    OPTIONAL MATCH (p)-[:OF_TYPE]->(t:TYPE)
                    OPTIONAL MATCH (t)-[:CONTAINS]->(f:FIELD)
                    RETURN m.source as method_source, 
                           p.index as param_index, 
                           p.name as param_name, 
                           p.type as param_type, 
                           collect({name: f.name, type: f.type}) as fields
                    ORDER BY param_index
                    """
                    params_result = self.db_client.execute_query(param_query, {"root_id": root_id})
                    
                    parameter_infos = []
                    for p_row in params_result:
                        # 현재는 간단한 스키마 구성 (재귀적 조회는 비용이 큼)
                        # 'fields'가 DTO 구조를 나타낸다고 가정하여 개선 가능
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

                    # 반환 타입 및 스키마 조회 (생략: 그래프에서 아직 지원되지 않음)
                    # return_query = ... 
                    return_type_name = "void"
                    return_schema = None

                    grouped_traces[root_id] = TraceResult(
                        root_method_id=root_id,
                        root_method_signature=root_node.get('signature', ''),
                        root_method_code=root_node.get('source', ''),
                        affected_methods=[affected_method],
                        parameters=parameter_infos,
                        return_type_name=return_type_name,
                        return_schema=return_schema
                    )

        trace_results = list(grouped_traces.values())
        logger.info(f"여러 대상을 포괄하는 {len(trace_results)}개의 고유 루트 경로를 추적했습니다.")
        return {"trace_results": trace_results}

    def summarize_context(self, state: AgentState) -> Dict[str, Any]:
        """
        LLM 컨텍스트 최적화를 위해 중간 노드 및 루트 메서드의 코드를 요약합니다.
        """
        traces = state.trace_results
        logger.info(f"{len(traces)}개 트레이스에 대한 컨텍스트 요약 중...")
        
        chain = SUMMARIZATION_PROMPT | self.llm | StrOutputParser()
        
        for trace in traces:
            # 1. 루트 메서드 요약
            try:
                root_summary = chain.invoke({
                    "signature": trace.root_method_signature, 
                    "code": trace.root_method_code[:4000] # Truncate safety
                })
                trace.root_method_summary = root_summary
            except Exception as e:
                logger.error(f"루트 요약 실패 {trace.root_method_signature}: {e}")
                trace.root_method_summary = "Summary failed."

            # 2. 경로 트레이스(중간 노드) 요약
            for am in trace.affected_methods:
                for node in am.path_trace:
                    try:
                        node_summary = chain.invoke({
                            "signature": node.signature,
                            "code": node.code[:4000]
                        })
                        node.summary = node_summary
                    except Exception as e:
                        logger.error(f"노드 요약 실패 {node.signature}: {e}")
                        node.summary = "Summary failed."
        
        logger.info("컨텍스트 요약 완료.")
        return {"trace_results": traces}



    def generate_scenarios(self, state: AgentState) -> Dict[str, Any]:
        """
        그룹화된 트레이스 결과를 기반으로 LLM을 사용하여 테스트 시나리오를 생성합니다.
        가능한 경우 원본 코드 대신 요약된 컨텍스트를 사용합니다.
        Critic 에이전트의 피드백 루프를 처리합니다.
        """
        traces = state.trace_results
        all_generated_scenarios = []
        
        logger.info(f"{len(traces)}개 루트 그룹에 대한 시나리오 생성 중...")
        
        parser = JsonOutputParser()
        chain = SCENARIO_GENERATION_PROMPT | self.llm | parser
        
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
                # 요약을 포함하여 영향을 받는 메서드 컨텍스트 포맷팅
                affected_methods_context = ""
                for idx, am in enumerate(trace.affected_methods):
                    # 경로 트레이스 (중간 노드)
                    path_context = ""
                    if am.path_trace:
                        path_context += "\n[Intermediate Path]:\n"
                        for p_node in am.path_trace:
                            path_context += f"  -> {p_node.signature}\n     (Summary: {p_node.summary})\n"
                    
                    affected_methods_context += f"""
--- Target Method {idx+1} ---
Signature: {am.signature}
{path_context}
Target Code:
{am.code[:2000]}...
"""
                
                # 루트 메서드 포맷팅 (가능한 경우 요약 + 부분 코드 사용)
                root_context = f"Signature: {trace.root_method_signature}\n"
                if trace.root_method_summary:
                    root_context += f"Summary: {trace.root_method_summary}\n"
                root_context += f"Code:\n{trace.root_method_code[:1000]}..." # Reduced code size due to summary

                # LLM 입력 준비
                inputs = {
                    "root_method": root_context,
                    "affected_methods_context": affected_methods_context,
                    "parameters": json.dumps([p.model_dump() for p in trace.parameters], indent=2, ensure_ascii=False),
                    "return_schema": json.dumps(trace.return_schema, indent=2, ensure_ascii=False) if trace.return_schema else "No Schema Available (void or primitive)",
                    "feedback": trace.feedback if trace.feedback else "None",
                    "previous_scenarios": json.dumps([s.model_dump() for s in trace.generated_scenarios], indent=2, ensure_ascii=False) if trace.generated_scenarios else "None"
                }
                
                result = chain.invoke(inputs)
                
                # 결과를 GeneratedScenario 객체로 파싱
                current_scenarios = []
                if isinstance(result, list):
                    for item in result:
                        scenario = GeneratedScenario(
                            test_case_id=f"TC-{len(all_generated_scenarios)+1:03d}", # Global ID not strictly unique per retry, but fine
                            test_case_name=item.get('test_case_name', 'No Name'),
                            step_no=item.get('step_no', 1),
                            description=item.get('description', ''),
                            pre_condition=item.get('pre_condition', ''),
                            procedure=item.get('procedure', ''),
                            expected_result=item.get('expected_result', ''),
                            scenario_id=f"SC-{i+1:03d}", # Same Scenario ID for same Root group
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
        
        parser = JsonOutputParser()
        chain = SCENARIO_EVALUATION_PROMPT | self.llm | parser
        
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
                affected_methods_context = ""
                for am in trace.affected_methods:
                    affected_methods_context += f"Signature: {am.signature}\nCode:\n{am.code[:1000]}\n"
                
                scenarios_text = json.dumps([s.model_dump() for s in trace.generated_scenarios], indent=2, ensure_ascii=False)
                
                result = chain.invoke({
                    "affected_methods_context": affected_methods_context,
                    "scenarios": scenarios_text
                })
                
                decision = result.get("decision", "PASS")
                score = result.get("score", 100)
                feedback = result.get("feedback", "")
                
                if decision == "FAIL" or score <= 80:
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

        return {"trace_results": traces} # State update to persist feedback

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
            trace_summary += f"- Entry Point: {tr.root_method_signature}\n"
            trace_summary += f"  - Affects: {len(tr.affected_methods)} methods\n"
        
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
