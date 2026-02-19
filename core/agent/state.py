from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class MethodNode(BaseModel):
    """Neo4j 메서드 노드 통합 정보 (Target + Root + Validation)"""
    id: str  # Neo4j 노드 Element ID
    name: str # 메서드 이름
    signature: str # 메서드 서명
    code: Optional[str] = None # 소스 코드 (Root나 Target인 경우 존재)
    status: Optional[str] = None # NEW, MODIFIED, UNCHANGED 등

class ParameterInfo(BaseModel):
    """타입 세부 정보를 포함한 파라미터 정보"""
    name: str
    type: str
    fields: List[Dict[str, str]] = []  # 내부 필드의 플랫 리스트 (사용되지 않음 또는 단순 사용)
    dto_schema: Optional[Dict[str, Any]] = None # 복잡한 DTO 구조를 위한 재귀적인 딕셔너리

class TestContext(BaseModel):
    """테스트 생성을 위한 컨텍스트 (Root Method와 연관된 Target Methods 그룹)"""
    root_method: MethodNode
    target_methods: List[MethodNode] = [] # 이 Root Method를 통해 도달 가능한 검증 대상 메서드들
    parameters: List[ParameterInfo] = []
    
    # 검증 및 피드백 루프 필드
    generated_scenarios: List['GeneratedScenario'] = [] # 이 컨텍스트에 특화된 시나리오
    feedback: Optional[str] = None # Critic 피드백
    retry_count: int = 0
    evaluation_passed: bool = False
    

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
    
    # Internal metadata
    root_method_signature: Optional[str] = None
    api_endpoint: Optional[str] = None

class AgentState(BaseModel):
    """
    에이전트 워크플로우를 위한 전역 상태.
    
    NOTE: LangGraph는 기본적으로 TypedDict를 권장하지만,
    Pydantic BaseModel도 호환됩니다. 향후 LangGraph 버전 업그레이드 시
    TypedDict로의 마이그레이션을 고려해야 합니다.
    """
    target_methods: List[MethodNode] = []
    test_contexts: List[TestContext] = []
    generated_scenarios: List[GeneratedScenario] = []
    test_strategy_summary: Optional[str] = None
