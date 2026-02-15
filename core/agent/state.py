from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class TargetMethod(BaseModel):
    """Neo4j 메서드 노드 정보"""
    id: str  # Neo4j 노드 Element ID (또는 유니크한 경우 서명)
    name: str
    signature: str
    status: str
    file_path: str

class ParameterInfo(BaseModel):
    """타입 세부 정보를 포함한 파라미터 정보"""
    name: str
    type: str
    fields: List[Dict[str, str]] = []  # 내부 필드의 플랫 리스트 (사용되지 않음 또는 단순 사용)
    dto_schema: Optional[Dict[str, Any]] = None # 복잡한 DTO 구조를 위한 재귀적인 딕셔너리

class MethodInfo(BaseModel):
    """호출 트레이스 내의 모든 메서드에 대한 정보"""
    id: str
    signature: str
    code: str
    summary: Optional[str] = None

class AffectedMethod(BaseModel):
    id: str
    signature: str
    code: str
    call_path: List[str] # 서명 리스트 (레거시 표시용)
    path_trace: List[MethodInfo] = [] # 전체 메서드 객체의 정렬된 리스트 (중간 노드)

class TraceResult(BaseModel):
    """루트에서 다중 타겟까지의 경로"""
    root_method_id: str
    root_method_signature: str
    root_method_code: str
    root_method_summary: Optional[str] = None
    affected_methods: List[AffectedMethod] = []
    parameters: List[ParameterInfo] = []
    return_type_name: Optional[str] = None
    return_schema: Optional[Dict[str, Any]] = None
    
    # 검증 및 피드백 루프 필드
    generated_scenarios: List['GeneratedScenario'] = [] # 이 트레이스에 특화된 시나리오
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

class AgentState(BaseModel):
    """에이전트 워크플로우를 위한 전역 상태"""
    target_methods: List[TargetMethod] = []
    trace_results: List[TraceResult] = []
    generated_scenarios: List[GeneratedScenario] = []
    test_strategy_summary: Optional[str] = None
    excel_file_path: str = ""
    errors: List[str] = []
