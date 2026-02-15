from langchain_core.prompts import PromptTemplate

SCENARIO_GENERATION_PROMPT = PromptTemplate(
    input_variables=["root_method", "affected_methods_context", "parameters", "return_schema", "feedback", "previous_scenarios"],
    template="""
You are an expert QA Engineer specializing in Integrated Test Scenarios.
Based on the modified source code and the Root Method (entry point) that calls it, you must generate or refine comprehensive integrated test scenarios in JSON format.

**Goal (API-Centric)**:
1. **If Root Method is an API Endpoint (Controller)**: You MUST write an executable `curl` command in the `procedure` field.
2. **JSON Body Construction**: Recursively analyze the `dto_schema` provided in `Parameters` to construct a valid JSON Body.
3. **JSON Response Construction**: Refer to the `Return Schema` to construct a realistic **JSON Object** in the `expected_result` field.

**Input Information**:
1. **Root Method** (Includes API Endpoint Info):
{root_method}

2. **Affected Methods Context** (Modified Logic):
{affected_methods_context}

3. **Parameters** (Includes DTO Schema):
{parameters}

4. **Return Schema** (Response Object Structure):
{return_schema}

**Critic Feedback Loop (Refinement Task)**:
- **Previous Scenarios**: 
{previous_scenarios}
- **Critic Feedback**: 
{feedback}

**Instructions**:
- If `Previous Scenarios` and `Feedback` are provided, your task is to **FIX** or **AUGMENT** the existing scenarios based on the feedback.
- **Do NOT regenerate valid scenarios** unless they are incorrect. You can reuse the JSON objects that are already correct.
- **Focus on Missing Cases**: If feedback says "Missing edge case", add THAT specific scenario.
- **Focus on Corrections**: If feedback says "Wrong expected result", fix THAT specific field.

**Output Requirements (JSON List)**:
- `test_case_name`: Write in **Korean**.
- `description`: Write in **Korean**.
- `pre_condition`: Write in **Korean**.
- `procedure`: **MUST be a `curl` command**.
    - For the JSON Body within the curl command, apply **newlines (\\n) and indentation** for readability.
    - (e.g., `curl ... -d '\\n{{\\n  "key": "value"\\n}}'`)
- `expected_result`: **MUST be a JSON format** response body example. (Minimize text explanation).

**Writing Guide**:
- **cURL**: Include the `-H "Content-Type: application/json"` header.
- **Expected Result**: Create a JSON example adhering to the field names and types in `Return Schema`.

**JSON Format Example**:
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
**CAUTION**: Output ONLY the JSON format. Do not include any explanations.
"""
)

TEST_STRATEGY_PROMPT = PromptTemplate(
    input_variables=["target_summary", "trace_summary"],
    template="""
You are a Lead Manager in Software Quality Assurance (QA).
Based on the analysis of modified source code and its impact scope, you must generate a **Comprehensive Test Strategy Report**.

**Goal**:
Analyze the impact of the changes on the entire system and clearly identify the test points and key risks that the QA team should focus on.
The report MUST be written in clear and concise **Korean**, understandable by both developers and non-developers.

**Input Information**:
1. **Change Summary (Targets)**:
{target_summary}

2. **Impact Scope & Entry Points (Trace Roots)**:
{trace_summary}

**Output Requirements (Markdown)**:
The report MUST follow this structure and be written in **Korean**:

### 1. 변경점 요약 (Changes)
- Summarize the key features and logic changed.
- Example: "**사용자 인증 로직**이 변경되어, 토큰 발급 방식이 수정되었습니다."

### 2. 영향도 분석 (Impact Analysis)
- List the major entry points (API, screens, etc.) affected by the changes.
- Example: "이 변경은 **로그인 API (`/login`)**와 **마이페이지 조회**에 직접적인 영향을 줍니다."

### 3. 주요 테스트 포인트 (Key Test Points)
- List the items that the QA team MUST verify.
- **Highlight important keywords in bold**.
- Example:
  - **유효하지 않은 토큰**으로 접근 시 차단 여부 검증
  - **세션 만료 시간** 이후 재요청 시나리오

**Style Guide**:
- Maintain a professional yet easy-to-understand tone.
- Omit unnecessary introductions/conclusions and deliver only the core content.
"""
)

SUMMARIZATION_PROMPT = PromptTemplate(
    input_variables=["signature", "code"],
    template="""
You are a Senior Developer summarizing code for a QA Engineer.
Your goal is to extract only the **Data Flow & Behavior** relevant for testing.

**Input Code**:
- Signature: `{signature}`
- Code:
{code}

**Task**:
Summarize the code in **Korean** within 3 bullet points, focusing on:
1. **Validation**: What inputs are rejected? (e.g., `if (x < 0) throw ...`)
2. **Transformation**: How is data modified? (e.g., `price * 1.1`, `DTO mapping`)
3. **Side Effects**: DB updates, External API calls, Logging, etc.

**Constraints**:
- Keep it under 3 lines.
- Do NOT explain basic syntax (e.g., "defines a function"). Only explain logic.
- If the code is trivial (e.g., getter/setter), just say "Simple Getter/Setter".
"""
)

SCENARIO_EVALUATION_PROMPT = PromptTemplate(
    input_variables=["scenarios", "affected_methods_context"],
    template="""
You are a strict **Test Critic (QA Auditor)**.
Your job is to evaluate the Generated Test Scenarios against the actual source code logic.

**Target Logic (Source Code)**:
{affected_methods_context}

**Generated Scenarios**:
{scenarios}

**Evaluation Criteria**:
1. **Coverage**: Do the tests cover the *changed logic*? (e.g., if code added `if x < 0`, is there a test for negative x?)
2. **Correctness**: Are the inputs/pre-conditions logically consistent? (e.g., Input `update` but Pre-condition `user not exists` -> Wrong)
3. **Completeness**: Are there missing edge cases?

**Task**:
- If the scenarios are GOOD (Score > 80), output `PASS`.
- If the scenarios are BAD (Score <= 80), output `FAIL` followed by specific **Feedback** for regeneration.

**Output Format (JSON)**:
{{
  "decision": "PASS" or "FAIL",
  "score": 85,
  "feedback": "Explain why it failed. Be specific about missing cases or wrong logic." (Leave empty if PASS)
}}
"""
)
