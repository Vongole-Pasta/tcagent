from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class TargetMethod(BaseModel):
    """Neo4j Method Node Information"""
    id: str  # Neo4j Node Element ID (or signature if unique)
    name: str
    signature: str
    status: str
    file_path: str

class ParameterInfo(BaseModel):
    """Parameter Information with Type Details"""
    name: str
    type: str
    fields: List[Dict[str, str]] = []  # Flat list of internal fields (deprecated or simple usage)
    dto_schema: Optional[Dict[str, Any]] = None # Recursive dictionary for complex DTO structure

class AffectedMethod(BaseModel):
    id: str
    signature: str
    code: str
    call_path: List[str]

class TraceResult(BaseModel):
    """Path from Root to Multiple Targets"""
    root_method_id: str
    root_method_signature: str
    root_method_code: str
    affected_methods: List[AffectedMethod] = []
    parameters: List[ParameterInfo] = []
    return_type_name: Optional[str] = None
    return_schema: Optional[Dict[str, Any]] = None

class GeneratedScenario(BaseModel):
    """Mapped to Excel 'VOD' Sheet Columns"""
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
    """Global State for the Agent Workflow"""
    target_methods: List[TargetMethod] = []
    trace_results: List[TraceResult] = []
    generated_scenarios: List[GeneratedScenario] = []
    test_strategy_summary: Optional[str] = None
    excel_file_path: str = ""
    errors: List[str] = []
