from typing import List, Dict, Any, Optional
import uuid
from pydantic import BaseModel, Field

class ParameterInfo(BaseModel):
    """타입 세부 정보를 포함한 파라미터 정보"""
    name: str
    type: str
    fields: List[Dict[str, str]] = []  # 내부 필드의 플랫 리스트 (사용되지 않음 또는 단순 사용)
    dto_schema: Optional[Dict[str, Any]] = None # 복잡한 DTO 구조를 위한 재귀적인 딕셔너리

class HeaderInfo(BaseModel):
    key: str = Field(description="The name of the HTTP header (e.g., 'Authorization', 'X-API-Key')")
    value: str = Field(description="A sample value or placeholder for the header")

class PayloadExtractionResult(BaseModel):
    """LLM이 추출한 순수 클라이언트 전송용 페이로드 및 헤더 정보"""
    payload_schema: Dict[str, Any] = Field(description="The JSON schema structure representing ONLY the data the client needs to send in the body or query.")
    required_headers: List[HeaderInfo] = Field(description="List of HTTP headers required for this request (e.g., Authorization due to interceptors/filters, or explicit @RequestHeader args).", default_factory=list)

class EvaluationResult(BaseModel):
    """LLM이 시나리오 평가 후 반환하는 결과 형식"""
    thought_process: str = Field(description="Step by step reasoning for the evaluation")
    decision: str = Field(description="'PASS' or 'FAIL'")
    score: int = Field(description="Score from 0 to 100")
    feedback: str = Field(description="Specific feedback if score < 100, otherwise empty")


class MethodNode(BaseModel):
    """Neo4j 메서드 노드 통합 정보 (Target + Root + Validation)"""
    id: str  # Neo4j 노드 Element ID
    name: str # 메서드 이름
    signature: str # 메서드 서명
    code: Optional[str] = None # 소스 코드 (Root나 Target인 경우 존재)
    status: Optional[str] = None # NEW, MODIFIED, UNCHANGED 등

class GeneratedScenario(BaseModel):
    """Excel 'VOD' 시트 컬럼 매핑"""
    test_case_id: str = Field(description="Column 1: Test Case ID")
    test_case_name: str = Field(description="Column 2: Test Case Name")
    step_no: int = Field(description="Column 3: Step No")
    description: str = Field(description="Column 4: Description")
    pre_condition: str = Field(description="Column 5: Pre-condition")
    procedure: str = Field(description="Column 6: Procedure")
    expected_result: str = Field(description="Column 7: Expected Result")
    scenario_id: str = Field(description="Column 17: Scenario ID")    
    root_method_signature: Optional[str] = None
    api_endpoint: Optional[str] = None

class TestContext(BaseModel):
    """테스트 생성을 위한 변하지 않는 구조적 컨텍스트 (Root Method와 연관된 Target Methods 및 Schema)"""
    context_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    root_method: MethodNode
    target_methods: List[MethodNode] = [] # 이 Root Method를 통해 도달 가능한 검증 대상 메서드들
    parameters: List[ParameterInfo] = []
    filtered_payloads: Optional[Dict[str, Any]] = None # 순수 클라이언트 데이터 스키마
    required_headers: List[HeaderInfo] = [] # 인증 등을 위한 필수 헤더 목록

class ScenarioGenerationState(BaseModel):
    """LLM 워크플로우를 거치며 생성, 평가, 갱신되는 가변적인 상태값"""
    context_id: str
    generated_scenarios: List[GeneratedScenario] = [] # 이 컨텍스트에 특화된 시나리오
    feedback: Optional[str] = None # Critic 피드백
    retry_count: int = 0
    evaluation_passed: bool = False

class AgentState(BaseModel):
    """
    에이전트 워크플로우를 위한 전역 상태.
    
    NOTE: LangGraph는 기본적으로 TypedDict를 권장하지만,
    Pydantic BaseModel도 호환됩니다. 향후 LangGraph 버전 업그레이드 시
    TypedDict로의 마이그레이션을 고려해야 합니다.
    """
    target_methods: List[MethodNode] = []
    test_contexts: List[TestContext] = []
    scenario_states: Dict[str, ScenarioGenerationState] = {} # context_id를 키로 가지는 맵
    generated_scenarios: List[GeneratedScenario] = []
    test_strategy_summary: Optional[str] = None
