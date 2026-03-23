import operator
from typing import List, Dict, Any, TypedDict, Annotated, NotRequired
from pydantic import BaseModel, Field

class ImpactGroup(TypedDict):
    """엔드포인트별 식별 및 컨텍스트 정보 (Path 객체 제외)"""
    url: str
    http_method: str
    name: str
    endpoint_qualnames: List[str]  # 엔드포인트 메서드 qualname 목록
    source_methods: List[str]     # 영향을 준 소스 메서드 ID 목록

class HappyCaseState(TypedDict):
    """
    에이전트의 전체 State를 정의합니다.
    NotRequired를 사용하여 필수 입력값이 아닌 필드들을 구분합니다.
    """
    source_method_ids: List[str]                 # 입력: 영향도 분석 시작점 (또는 직접 선택한 엔드포인트)
    
    impact_groups: NotRequired[Dict[str, ImpactGroup]] # 분석 결과: 식별된 엔드포인트 그룹 (key: "HTTP_METHOD:URL")
    # Annotated[..., operator.add]: 병렬 워커들이 반환하는 리스트를 메인 State에 자동으로 누적합니다.
    worker_results: Annotated[NotRequired[List[Dict[str, Any]]], operator.add] # 각 워커의 생성 결과물 (최종 집계용)
    scenarios: NotRequired[List[Dict[str, Any]]]       # 최종 결과물 (TC-001 등 ID 부여 완료)
    # 여러 워커에서 발생한 에러를 하나의 리스트로 합칩니다 (Reducer 적용).
    errors: Annotated[NotRequired[List[str]], operator.add]

class WorkerState(TypedDict):
    """
    개별 엔드포인트 작업을 위한 State입니다.
    retriever -> generator 순서로 데이터가 전달됩니다.
    """
    group: ImpactGroup
    context: NotRequired[Dict[str, Any]]         # retriever가 수집한 메서드/DTO 컨텍스트
    worker_results: Annotated[NotRequired[List[Dict[str, Any]]], operator.add]  # 생성된 최종 결과 (시나리오)
    errors: Annotated[NotRequired[List[str]], operator.add]  # 워커에서 발생한 에러 기록

import json
from pydantic import BaseModel, Field, field_validator

class HappyCaseOutput(BaseModel):
    """LLM이 생성할 Happy Case 시나리오 구조 (요구사항 반영)"""
    test_case: str = Field(description="해당 API의 기능 위주로 한국어로 설명 (성공 케이스)")
    input_data: str = Field(description="입력 데이터 정보를 지정된 마크다운 리스트 형식으로 작성한 문자열")
    expected_result: str = Field(description="성공 시 예상되는 응답 데이터를 지정된 마크다운 리스트 형식으로 작성한 문자열")


    @field_validator('input_data', 'expected_result', mode='before')
    @classmethod
    def format_json_string(cls, v):
        """
        LLM이 무리하게 감싼 마크다운 백틱(```json)이나 
        최외곽의 불필요한 따옴표를 백엔드에서 1차적으로 걷어냅니다.
        """
        if not isinstance(v, str):
            try: return json.dumps(v, ensure_ascii=False, indent=2)
            except: return str(v)
            
        cleaned = v.strip()
        return cleaned
