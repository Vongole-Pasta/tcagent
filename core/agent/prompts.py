from langchain_core.prompts import PromptTemplate

SCENARIO_GENERATION_PROMPT = PromptTemplate(
    input_variables=["root_method", "affected_methods_context", "parameters"],
    template="""
당신은 통합 테스트 시나리오를 작성하는 전문 QA 엔지니어입니다.
변경된 소스 코드와 이를 호출하는 최상위 진입점(Root Method)의 정보를 바탕으로,
통합 테스트 시나리오를 작성하여 JSON 형식으로 출력해야 합니다.

**목표**:
**목표**:
동일한 진입점(`root_method`) 하위에서 변경된 여러 로직들(`affected_methods_context`)을 분석하여,
각 변경 사항을 검증할 수 있는 통합 테스트 시나리오들을 도출하세요.
각 변경된 메소드(Target)별로 최소 1개 이상의 테스트 케이스가 포함되어야 합니다.

**입력 정보**:
1. **Root Method** (테스트 진입점):
{root_method}

2. **Affected Methods Context** (변경된 메소드들 및 호출 경로):
{affected_methods_context}

4. **Parameters** (입력 데이터 구조):
{parameters}

**출력 요구사항 (JSON List)**:
다음 항목을 포함하는 JSON 객체의 리스트를 작성하세요. (최소 1개 이상)
각 필드는 엑셀의 특정 컬럼에 매핑됩니다.

- `test_case_name` (Test Case Name): 테스트 케이스의 요약 제목.
- `step_no` (Step No): 단계 번호 (1부터 시작).
- `description` (Description): 테스트 수행 절차 상세 설명.
- `pre_condition` (Pre-condition): 테스트 수행 전 만족해야 할 조건 (DB 상태, 설정 등).
- `procedure` (Procedure): 구체적인 입력 데이터나 실행해야 할 API/SQL 등.
- `expected_result` (Expected Result): 테스트 수행 후 기대되는 결과.

**작성 가이드**:
- **언어**: 한국어(Korean)로 작성하세요.
- **Pre-condition**: 코드 로직에서 유추 가능한 필수 조건(예: 특정 상태값, 데이터 존재 여부)을 명시하세요.
- **Procedure**: `Parameters` 정보를 참고하여 구체적인 입력값 예시(JSON 등)를 포함하세요.
- **Expected Result**: 변경된 로직(`modified_method`)이 수행되었음을 확인할 수 있는 결과(로그, DB 변경, 리턴값)를 기술하세요.

**JSON 형식 예시**:
```json
[
  {{
    "test_case_name": "사용자 생성 성공 테스트",
    "step_no": 1,
    "description": "유효한 사용자 정보를 입력하여 생성을 요청한다.",
    "pre_condition": "동일한 ID의 사용자가 존재하지 않아야 함.",
    "procedure": "POST /api/users {{ 'id': 'test', 'name': '홍길동' }}",
    "expected_result": "HTTP 200 OK 및 DB에 사용자 정보 저장됨."
  }}
]
```

**주의**: JSON 포맷만 출력하세요. 다른 설명은 포함하지 마세요.
"""
)
