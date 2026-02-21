
import logging
import json
import re
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from pydantic import BaseModel, Field

from config import Config
from infra.db_client import DBClient
from graph_db.queries import CypherQueries
from core.agent.state import AgentState, MethodNode, TestContext, GeneratedScenario, PayloadExtractionResult, EvaluationResult
from core.agent.prompts import SCENARIO_GENERATION_PROMPT, TEST_STRATEGY_PROMPT, SCENARIO_EVALUATION_PROMPT, PAYLOAD_EXTRACTION_PROMPT

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
        results = self.db_client.execute_query(CypherQueries.GET_TARGET_METHODS)
        
        targets = []
        for row in results:
            targets.append(MethodNode(
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
        # Key: root_method_id, Value: TestContext
        grouped_contexts: Dict[str, TestContext] = {}
        
        try:
            for target in targets:
                # 루트 메서드(프로젝트 컨텍스트 내에서 다른 메서드에 의해 호출되지 않는 메서드)를 찾습니다.
                # 또는 명시적인 컨트롤러 엔드포인트인 메서드를 찾습니다.
                # 단순화를 위해 가장 긴 상위 경로를 찾습니다.
                paths = self.db_client.execute_query(CypherQueries.TRACE_ROOT_METHODS, {"target_id": target.id})
                
                for row in paths:
                    root_node = row['root']
                    target_node = row['target']
                    
                    root_id = root_node.element_id
                    
                    # MethodNode (Target) 객체 생성
                    # 최적화: 루트 메서드와 동일한 경우 코드를 중복 저장하지 않음 (토큰 절약)
                    is_root_duplicate = (target_node.element_id == root_id)
                    
                    target_method_node = MethodNode(
                        id=target_node.element_id,
                        name=target_node.get('name', ''),
                        signature=target_node.get('signature', ''),
                        code="" if is_root_duplicate else target_node.get('source', ''),
                        status=target_node.get('status', '')
                    )

                    if root_id in grouped_contexts:
                        # 고유한 경우 기존 컨텍스트에 추가
                        existing = grouped_contexts[root_id]
                        if not any(tm.id == target_method_node.id for tm in existing.target_methods):
                            existing.target_methods.append(target_method_node)
                    else:
                        # 루트 메서드 컨텍스트를 위한 파라미터 조회 (루트당 한 번만)
                        # 업데이트된 쿼리: 어노테이션 및 DTO 필드 조회
                        params_result = self.db_client.execute_query(CypherQueries.GET_ROOT_PARAMETERS, {"root_id": root_id})
                        
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



                        root_method_node = MethodNode(
                            id=root_id,
                            name=root_node.get('name', ''),
                            signature=root_node.get('signature', ''),
                            code=root_node.get('source', ''),
                            status=root_node.get('status', '')
                        )

                        grouped_contexts[root_id] = TestContext(
                            root_method=root_method_node,
                            target_methods=[target_method_node],
                            parameters=parameter_infos
                        )

        except Exception as e:
            import traceback
            logger.error(f"trace_roots 중 치명적 오류 발생: {e}")
            traceback.print_exc()
            raise e

        test_contexts = list(grouped_contexts.values())
        logger.info(f"여러 대상을 포괄하는 {len(test_contexts)}개의 고유 루트 경로를 추적했습니다.")
        return {"test_contexts": test_contexts}

    def extract_payloads(self, state: AgentState) -> Dict[str, Any]:
        """
        루트 메서드의 전체 파라미터에서 클라이언트가 전송해야 하는 순수 페이로드와 필수 헤더를 추출합니다.
        """
        contexts = state.test_contexts
        logger.info(f"{len(contexts)}개 루트 그룹에 대한 Payload 추출 중...")
        
        parser = JsonOutputParser(pydantic_object=PayloadExtractionResult)
        chain = PAYLOAD_EXTRACTION_PROMPT | self.llm | parser
        
        for i, ctx in enumerate(contexts):
            # 이미 추출되었거나 평가 통과한 경우 스킵
            if ctx.filtered_payloads is not None or ctx.evaluation_passed:
                continue
                
            try:
                root_code = ctx.root_method.code if ctx.root_method.code else "(No Code)"
                params_json = json.dumps([p.model_dump(exclude_none=True) for p in ctx.parameters], indent=2, ensure_ascii=False)
                
                inputs = {
                    "root_method_code": root_code[:2000],
                    "raw_parameters": params_json,
                    "format_instructions": parser.get_format_instructions()
                }
                
                result = chain.invoke(inputs)
                
                # PayloadExtractionResult 형태로 저장
                ctx.filtered_payloads = result.get('payload_schema', {})
                
                # Pydantic v2 Serialization Warning 방지: dict를 HeaderInfo 객체로 명시적 변환
                raw_headers = result.get('required_headers', [])
                ctx.required_headers = [HeaderInfo(**h) if isinstance(h, dict) else h for h in raw_headers]
                
                logger.info(f"트레이스 {i} Payload 추출 성공. headers: {len(ctx.required_headers)}개")
                
            except Exception as e:
                logger.error(f"트레이스 {i} Payload 추출 실패: {e}")
                # 기본값 폴백 (원본 유지)
                ctx.filtered_payloads = {}
                ctx.required_headers = []
                
        return {"test_contexts": contexts}

    def generate_scenarios(self, state: AgentState) -> Dict[str, Any]:
        """
        그룹화된 트레이스 결과를 기반으로 LLM을 사용하여 테스트 시나리오를 생성합니다.
        가능한 경우 원본 코드 대신 요약된 컨텍스트를 사용합니다.
        Critic 에이전트의 피드백 루프를 처리합니다.
        """
        contexts = state.test_contexts
        all_generated_scenarios = []
        
        logger.info(f"{len(contexts)}개 루트 그룹에 대한 시나리오 생성 중...")
        
        parser = JsonOutputParser()
        chain = SCENARIO_GENERATION_PROMPT | self.llm | parser
        
        for i, ctx in enumerate(contexts):
            # 이미 평가를 통과한 경우 건너뜀
            if ctx.evaluation_passed:
                all_generated_scenarios.extend(ctx.generated_scenarios)
                continue
            
            # 재시도 제한에 도달한 경우 건너뜀 (이전 결과 수용)
            if ctx.retry_count >= 2 and ctx.generated_scenarios:
                logger.warning(f"트레이스 {i} 재시도 제한 도달. 현재 시나리오 수용.")
                ctx.evaluation_passed = True
                all_generated_scenarios.extend(ctx.generated_scenarios)
                continue

            try:
                validation_context = ""
                for idx, tm in enumerate(ctx.target_methods):
                    # 코드 가져오기 (최적화된 경우 루트 코드 사용)
                    tm_code = tm.code
                    if not tm_code and tm.id == ctx.root_method.id:
                        tm_code = f"(Root Method Code와 동일)\n{ctx.root_method.code[:2000]}"
                    elif not tm_code:
                        tm_code = "(코드 없음)"
                    else:
                        tm_code = tm_code[:2000]

                    validation_context += f"""
--- Target Method {idx+1} ---
Signature: {tm.signature}
Target Code:
{tm_code}...
"""
                
                # 루트 메서드 포맷팅 (가능한 경우 요약 + 부분 코드 사용)
                root_context = ""
                root_context += f"Signature: {ctx.root_method.signature}\n"
                root_context += f"Code:\n{ctx.root_method.code[:1000]}..."

                # LLM 입력 준비 (최적화: None 값 제외 및 불필요 메타데이터 제거)
                
                # 1. 파라미터 최적화 (이전에는 전체를 보냈지만 이제 필터링된 페이로드와 헤더를 보냄)
                payload_schema_json = json.dumps(ctx.filtered_payloads if ctx.filtered_payloads is not None else {}, indent=2, ensure_ascii=False)
                required_headers_json = json.dumps(ctx.required_headers if ctx.required_headers else [], indent=2, ensure_ascii=False)
                
                # 2. 이전 시나리오 요약 (재시도 시 전체 덤프 대신 핵심 필드만 전달)
                previous_scenarios_json = "None"
                if ctx.generated_scenarios:
                    summary_list = []
                    for s in ctx.generated_scenarios:
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
                    "payload_schema": payload_schema_json,
                    "required_headers": required_headers_json,
                    "feedback": ctx.feedback if ctx.feedback else "None",
                    "previous_scenarios": previous_scenarios_json,
                    "format_instructions": "Return a valid JSON array of objects. Do NOT include markdown blocks like ```json."
                }
                
                try:
                    result = chain.invoke(inputs)
                except Exception as e:
                    logger.error(f"트레이스 {i} 시나리오 생성/파싱 실패: {e}")
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
                            root_method_signature=ctx.root_method.signature,
                            api_endpoint=item.get('api_endpoint')
                        )
                        current_scenarios.append(scenario)
                
                # Update Trace Result
                ctx.generated_scenarios = current_scenarios
                all_generated_scenarios.extend(current_scenarios)
                logger.info(f"루트 그룹 {i+1}에 대해 {len(current_scenarios)}개의 시나리오 생성됨")
                
            except Exception as e:
                logger.error(f"트레이스 {i} 시나리오 생성 실패: {e}")
                # 이전 결과가 있으면 유지
                if ctx.generated_scenarios:
                    all_generated_scenarios.extend(ctx.generated_scenarios)
                    
        return {"generated_scenarios": all_generated_scenarios, "test_contexts": contexts}

    def evaluate_scenarios(self, state: AgentState) -> Dict[str, Any]:
        """
        Critic 노드: 생성된 시나리오를 평가하고 피드백을 제공합니다.
        """
        contexts = state.test_contexts
        logger.info("시나리오 평가 중 (Critic 모드)...")
        
        parser = JsonOutputParser(pydantic_object=EvaluationResult)
        chain = SCENARIO_EVALUATION_PROMPT | self.llm | parser
        
        has_failure = False
        
        for i, ctx in enumerate(contexts):
            if ctx.evaluation_passed:
                continue
                
            if not ctx.generated_scenarios:
                continue

            # 재시도 제한 도달 시 건너뜀
            if ctx.retry_count >= 2:
                ctx.evaluation_passed = True
                continue

            try:
                # Critic을 위한 컨텍스트 준비
                validation_context = ""
                
                # 1. Root Method (Entry Point) 정보 추가 - URL 매핑 및 진입점 로직 확인용
                validation_context += f"--- Root Method (Entry Point) ---\n"
                validation_context += f"Signature: {ctx.root_method.signature}\n"
                # Root Code는 URL 매핑과 초기 로직 확인을 위해 필수적임
                if ctx.root_method.code:
                    validation_context += f"Code:\n{ctx.root_method.code[:3000]}\n\n"
                else:
                    validation_context += "Code: (Not Available)\n\n"

                # 2. Target Methods (Changed Logic) 정보 추가 - 실제 변경된 비즈니스 로직 확인용
                for tm in ctx.target_methods:
                    validation_context += f"--- Target Method (Changed Logic: {tm.name}) ---\n"
                    validation_context += f"Signature: {tm.signature}\n"
                    if tm.code:
                        validation_context += f"Code:\n{tm.code[:2000]}\n\n"
                    else:
                        validation_context += "Code: (Not Available)\n\n"
                
                scenarios_text = json.dumps([s.model_dump() for s in ctx.generated_scenarios], indent=2, ensure_ascii=False)
                
                try:
                    result = chain.invoke({
                        "validation_context": validation_context,
                        "scenarios": scenarios_text,
                        "format_instructions": parser.get_format_instructions()
                    })
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
                    ctx.evaluation_passed = False
                    ctx.feedback = feedback
                    ctx.retry_count += 1
                    has_failure = True
                else:
                    logger.info(f"트레이스 {i} 평가 통과. 점수: {score}.")
                    ctx.evaluation_passed = True
                    ctx.feedback = None
            
            except Exception as e:
                logger.error(f"트레이스 {i} 평가 실패: {e}")
                # Critic 실패 시 통과로 가정
                ctx.evaluation_passed = True

        return {"test_contexts": contexts} # 피드백 상태 반영을 위한 업데이트

    def synthesize_strategy(self, state: AgentState) -> Dict[str, Any]:
        """
        식별된 대상 및 루트를 기반으로 테스트 전략 요약을 생성합니다.
        """
        targets = state.target_methods
        contexts = state.test_contexts
        
        logger.info(f"{len(targets)}개 대상 및 {len(contexts)}개 루트에 대한 전략 합성 중...")
        
        # 1. 대상 요약
        target_summary = ""
        for t in targets:
            target_summary += f"- [{t.status}] {t.name} ({t.signature})\n"
        
        # 2. 루트 요약
        trace_summary = ""
        for ctx in contexts:
            entry_point = ctx.root_method.signature
            
            # API Endpoint 정보 추가 (시나리오 생성 결과 기반)
            api_info = ""
            if ctx.generated_scenarios:
                # 첫 번째 시나리오의 엔드포인트를 사용하거나, 고유한 엔드포인트들을 나열
                endpoints = set(s.api_endpoint for s in ctx.generated_scenarios if s.api_endpoint)
                if endpoints:
                    api_info = f" (API: {', '.join(endpoints)})"
            
            trace_summary += f"- Entry Point: {entry_point}{api_info}\n"
            trace_summary += f"  - Target Methods: {len(ctx.target_methods)} methods\n"
        
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
