from langchain_core.prompts import PromptTemplate

SCENARIO_GENERATION_PROMPT = PromptTemplate(
    input_variables=["root_method", "affected_methods_context", "parameters", "return_schema"],
    template="""
당신은 통합 테스트 시나리오를 작성하는 전문 QA 엔지니어입니다.
변경된 소스 코드와 이를 호출하는 최상위 진입점(Root Method)의 정보를 바탕으로,
통합 테스트 시나리오를 작성하여 JSON 형식으로 출력해야 합니다.

**목표 (API 중심)**:
1. **Root Method가 API 엔드포인트(Controller)인 경우**: 반드시 실행 가능한 `curl` 명령어를 `procedure` 필드에 작성하세요.
2. **JSON Body 구성**: `Parameters` 정보에 포함된 `dto_schema`를 참조하여 재귀적으로 필드를 분석하고, 유효한 JSON Body를 구성하세요.
3. **JSON Response 구성**: `Return Schema` 정보를 참조하여 `expected_result` 필드에 실제 응답과 유사한 **JSON 객체**를 작성하세요.

**입력 정보**:
1. **Root Method** (API 엔드포인트 정보 포함):
{root_method}

2. **Affected Methods Context** (변경된 로직):
{affected_methods_context}

3. **Parameters** (DTO 스키마 포함):
{parameters}

4. **Return Schema** (응답 객체 구조):
{return_schema}

**출력 요구사항 (JSON List)**:
- `procedure`: **반드시 `curl` 명령어 형식**으로 작성해야 합니다.
    - JSON Body 부분은 **가독성을 위해 줄바꿈(\n)과 들여쓰기**를 적용하여 작성하세요.
    - (예: `curl ... -d '\n{{\n  "key": "value"\n}}'`)
- `expected_result`: **반드시 JSON 형식**의 응답 본문 예시를 포함해야 합니다. (텍스트 설명 최소화)

**작성 가이드**:
- **cURL**: `-H "Content-Type: application/json"` 헤더를 포함하세요.
- **Expected Result**: `Return Schema`의 필드명과 타입을 준수하여 JSON 예시를 만드세요.

**JSON 형식 예시**:
```json
[
  {{
    "test_case_name": "사용자 생성 성공",
    "step_no": 1,
    "description": "올바른 사용자 정보를 입력하여 생성을 요청한다.",
    "pre_condition": "중복된 ID가 없어야 함.",
    "procedure": "curl -X POST http://localhost:8080/api/users -H 'Content-Type: application/json' -d '\\n{{\\n  \"id\": \"test\",\\n  \"age\": 25\\n}}'",
    "expected_result": "{{\"res_msg\": \"성공\", \"data\": {{\"user_id\": \"test\", \"created_at\": \"2024-01-01\"}}, \"res_code\": \"200\"}}"
  }}
]
```
**주의**: JSON 포맷만 출력하세요. 설명은 생략합니다.
"""
)

TEST_STRATEGY_PROMPT = PromptTemplate(
    input_variables=["target_summary", "trace_summary"],
    template="""
당신은 소프트웨어 품질 관리(QA) 분야의 수석 매니저입니다.
개발 팀에서 변경된 소스 코드와 그 영향 범위를 분석한 결과를 바탕으로, **종합적인 테스트 전략 보고서**를 작성해야 합니다.

**목표**:
이번 변경 사항이 전체 시스템에 미치는 영향을 분석하고, QA 팀이 집중해야 할 테스트 포인트와 리스크를 명확히 제시하세요.
개발자나 비개발자 모두 이해할 수 있도록 명확하고 간결한 한국어로 작성해야 합니다.

**입력 정보**:
1. **변경 내역 요약 (Targets)**:
{target_summary}

2. **영향 범위 및 진입점 (Trace Roots)**:
{trace_summary}

**출력 요구사항 (Markdown)**:
보고서는 다음 구조를 반드시 따라야 합니다:

### 1. 변경점 요약 (Changes)
- 변경된 주요 기능과 로직을 요약합니다.
- 예: "**사용자 인증 로직**이 변경되어, 토큰 발급 방식이 수정되었습니다."

### 2. 영향도 분석 (Impact Analysis)
- 변경 사항이 영향을 미치는 주요 진입점(API, 화면 등)을 나열합니다.
- 예: "이 변경은 **로그인 API (`/login`)**와 **마이페이지 조회**에 직접적인 영향을 줍니다."

### 3. 주요 테스트 포인트 (Key Test Points)
- QA 팀이 반드시 검증해야 할 항목을 리스트업 합니다.
- **중요한 키워드는 굵게(**bold**) 표시**하세요.
- 예:
  - **유효하지 않은 토큰**으로 접근 시 차단 여부 검증
  - **세션 만료 시간** 이후 재요청 시나리오

**스타일 가이드**:
- 전문적이지만 이해하기 쉬운 톤앤매너를 유지하세요.
- 불필요한 서론/결론은 생략하고 핵심 내용만 전달하세요.
"""
)
