from langchain_core.prompts import PromptTemplate

SCENARIO_GENERATION_PROMPT = PromptTemplate(
    input_variables=["root_method", "affected_methods_context", "parameters", "return_schema", "feedback", "previous_scenarios"],
    template="""
Role: Expert QA Engineer.
Goal: Generate integrated test scenarios (API-centric) for modified code in JSON format.

**Input Context**:
1. Root Method (Entry Point): {root_method}
2. Modified Logic (Target/Path): {affected_methods_context}
3. Parameters (DTO Schema): {parameters}
4. Return Schema: {return_schema}
5. Feedback (if retry): {feedback} / Previous Scenarios: {previous_scenarios}

**Instructions**:
- If Feedback exists, FIX or AUGMENT previous scenarios strictly. Otherwise, generate new ones.
- **Procedure**: MUST be a valid `curl` command with `-H 'Content-Type: application/json'`.
  - JSON Body inside curl: Use `\\n` and indentation for readability.
- **Expected Result**: VALID JSON object matching Return Schema.
- **Language**: Use **Korean** for Name, Description, Pre-condition.

**Output Format (JSON List ONLY)**:
Make sure to follow this JSON structure exactly:
```json
[
  {{
    "test_case_name": "사용자 생성 성공",
    "step_no": 1,
    "description": "올바른 사용자 정보를 입력하여 생성을 요청한다.",
    "pre_condition": "중복된 ID가 없어야 함.",
    "procedure": "curl -X POST http://localhost:8080/api/users -H 'Content-Type: application/json' -d '\\n{{\\n  \"id\": \"test\",\\n  \"age\": 25\\n}}'",
    "expected_result": "{{\"res_msg\": \"성공\", \"data\": {{\"user_id\": \"test\"}}, \"res_code\": \"200\"}}"
  }}
]
```
"""
)

TEST_STRATEGY_PROMPT = PromptTemplate(
    input_variables=["target_summary", "trace_summary"],
    template="""
Role: QA Lead Manager.
Language: **KOREAN (Must)**.
Goal: Create a concise Test Strategy Report based on changes.

**Inputs**:
- Targets: {target_summary}
- Entry Points: {trace_summary}

**Report Structure (Markdown)**:
### 1. 변경점 요약 (Changes)
- Summarize key logic changes.

### 2. 영향도 분석 (Impact Analysis)
- List affected API/Entry points.

### 3. 주요 테스트 포인트 (Key Test Points)
- List critical verification items (**Bold** keywords).
"""
)

SUMMARIZATION_PROMPT = PromptTemplate(
    input_variables=["signature", "code"],
    template="""
Task: Summarize code for QA in **Korean**.
Focus: Validation, Transformation, Side Effects only.
Constraint: Max 3 lines. No syntax explanation.

**Code**:
{signature}
{code}

**Summary**:
"""
)

SCENARIO_EVALUATION_PROMPT = PromptTemplate(
    input_variables=["scenarios", "affected_methods_context"],
    template="""
Role: QA Lead Auditor.
Task: Evaluate test scenarios against changed code.

**Context**:
- Scenarios: {scenarios}
- Changed Code: {affected_methods_context}

**Scoring Criteria**:
- **100 (Perfect)**: Covers ALL changed logic, edge cases, and exception handling perfectly.
- **90-99 (Excellent)**: Covers main logic well, but minor improvements possible.
- **80-89 (Good/Pass)**: Covers core happy paths, but misses some edge cases.
- **< 80 (Fail)**: Misses critical logic or assertions are incorrect.

**Evaluation Focus**:
1. **Validation Logic**: Does it test invalid inputs (null, empty, max length, special chars)?
2. **Business Logic**: Does it verify the specific changes in the target code?
3. **Edge Cases**: Does it cover boundary values (min/max)?

**Instructions**:
1. Analyze if scenarios cover the specific changes in the code.
2. If the scenarios are sufficient for the given code changes, give **100 points**. Do not deduct points arbitrarily.
3. Be specific in feedback if score < 100.

**Output (JSON)**:
{{
  "thought_process": "Step-by-step reasoning checking Validation, Business Logic, and Edge Cases...",
  "decision": "PASS" (Score >= 80) or "FAIL",
  "score": <0-100>,
  "feedback": "Feedback in Korean (Required if not 100)."
}}
"""
)
