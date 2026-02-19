from langchain_core.prompts import PromptTemplate

SCENARIO_GENERATION_PROMPT = PromptTemplate(
    input_variables=["root_method", "validation_context", "parameters", "feedback", "previous_scenarios"],
    template="""
Role: Senior API Testing Engineer.
Goal: Generate execution-ready `curl` commands to verify the **Specific Logic** in the Changed Code.

**Input Context**:
1. **Root Method (Entry Point)**: {root_method}
   - **USE THIS FOR STRUCTURE**: This defines the API Endpoint (URL, HTTP Method) and Request Body Schema.
   - **CRITICAL**: Analyze the code/annotations to extract the **HTTP Method** and **URL** (e.g., `@PostMapping("/api/test")` -> `POST /api/test`).
2. **Parameters (DTO Schema)**: {parameters}
   - **USE THIS FOR FIELDS**: Detailed JSON structure.
3. **Target Method (Changed Logic)**: {validation_context}
   - **USE THIS FOR VALUES**: The specific logic that needs verification.
   - **CRITICAL**: The generated request MUST trigger this specific logic.
4. **Feedback**: {feedback} / **Previous**: {previous_scenarios}

**Instructions**:
1. **Analyze Structure (Root)**: 
   - Identify the correct JSON Body structure based on `Root Method` and `Parameters`.
   - **Extract API Endpoint**: Determine the explicit **HTTP Method** and **URL** from the root method's code. If dynamic (e.g., `{{id}}`), use a placeholder or example value.
2. **Analyze Logic (Target)**: Identify the **Specific Values** required to trigger the `Target Method`'s logic. (e.g., if target checks `status == "VOID"`, input JSON must allow this value to pass).
3. **Generate Scenarios**:
   - Create **MULTIPLE** scenarios if the Changed Logic has distinct branches.
   - Focus on **Valid Requests (Happy Path)** that exercise the change.
4. **Generate `curl`**:
   - MUST be a valid, executable command.
   - MUST use `-H 'Content-Type: application/json'`.
   - **Payload Strategy**: Use `Root Method` for structure, `Target Method` for values.
5. **Language**: Use **Korean** for Name, Description, Pre-condition.

**Output Format (JSON List ONLY)**:
Following is an example of the desired output structure (Few-Shot Learning).
**NOTE**: The examples below are for **Structure Reference ONLY**.
- `api_endpoint`: The extracted HTTP Method and URL (e.g., "POST /api/v1/users").
- **Expected Result**: MUST be specific. logic-based.
   - **GOOD**: "Returns JSON {{'status':'error'}} AND logs 'Invalid ID' error."
   - **BAD**: "Request succeeds." or "Returns 200 OK."

```json
[
  {{
    "api_endpoint": "POST /V100/VMS_90002/drop_table",
    "test_case_name": "단기 영상테이블 삭제 (Example)",
    "step_no": 1,
    "description": "현재기준 longTableCycle 이전의 날짜의 테이블을 DROP한다.",
    "pre_condition": "config_properties.xml : vod.table.partition.long.yn 값이 'Y'",
    "procedure": "curl -X POST -H 'Content-Type:application/json' http://vms-vod:18080/V100/VMS_90002/drop_table? -d '{{\"user_id\":\"9999999999\",\"cam_id\":\"D99999999999999\",\"user_cam_code\":\"999999999\"}}'",
    "expected_result": "HTTP 200 OK 응답. 서버 로그에 'Drop table VMS_90002 success' 메시지가 출력되어야 함."
  }},
  {{
    "api_endpoint": "POST /V100/VMS_45001/recorded_video_url",
    "test_case_name": "녹화영상 조회 (Valid)",
    "step_no": 1,
    "description": "단기 영상데이터를 조회한다.",
    "pre_condition": "config_properties.xml : vod.table.partition.long.yn 값이 'N'",
    "procedure": "curl -X POST http://10.10.10.10:18080/V100/VMS_45001/recorded_video_url -H 'Content-Type: application/json' -d '{{\"user_id\": \"P_USER_ID\", \"secure_yn\": \"Y\", \"cam_info\": [{{\"cam_id\": \"P_CAM_ID\", \"playlist_yn\": \"N\", \"search_datetime_info\": [{{\"start_time\": \"20230626000000\", \"end_time\": \"20230626235959\"}}]}}]}}'",
    "expected_result": "응답 바디에 '\"res_msg\":\"성공\"' 및 '\"list\":[...]' 데이터가 포함되어야 함."
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
Goal: Create a concise Test Strategy Report regarding the changes.

**Inputs**:
- Targets: {target_summary}
- Entry Points: {trace_summary}

**Report Structure (Markdown)**:
### 1. 변경점 요약 (Changes)
- Summarize key logic changes briefly.

### 2. 영향도 분석 (Impact Analysis)
- List ALL affected API endpoints comprehensively.

### 3. 주요 테스트 포인트 (Key Test Points)
- List critical verification items (**Bold** keywords).
"""
)

SCENARIO_EVALUATION_PROMPT = PromptTemplate(
    input_variables=["scenarios", "validation_context"],
    template="""
Role: Lead Auditor (Conditional Strict Verification).
Language: Korean (for feedback).
Task: Verify if the generated test scenarios are **Factually Correct** based on the provided Source Code.

**Input Context**:
{validation_context}

**Scenarios to Verify**:
{scenarios}

**Evaluation Criteria (IMPORTANT: Be Flexible if Code is simple)**:

1. **Procedure Verification (Url & Method)**:
   - **Review Root Method Code**: Does it have `@RequestMapping`, `@PostMapping`, or `@GetMapping` annotations?
   - **YES**: The `curl` command MUST match these annotations exactly. (**FAIL** if mismatch).
   - **NO (Missing Annotations)**: Do NOT automatically Pass.
     - Check if the method has parameters with `@RequestBody` or similar object arguments.
     - **YES**: The `curl` command MUST include a JSON body matching those arguments. (**FAIL** if body is missing or mismatched).
     - **NO**: Only then, treat as **PASS** (assuming internal method or GET request).

2. **Expected Result Verification (Logs & Returns)**:
   - **Review Source Code**: Does it contain `logger.info(...)`, `return ...`, or `throw ...` statements?
   - **YES (Artifacts Exist)**: The "Expected Result" MUST mention these specific logs or return values. (**FAIL** if vague).
   - **NO (Void/No Logs)**: Do **NOT** Fail for generic success messages (e.g., "HTTP 200 OK"). If the code does nothing visible, a simple success expectation is acceptable.

3. **Logic Relevance**:
   - Does the input payload appear to target the specific logic parameters in the **Target Method**?

**Output Format (JSON)**:
{{
  "thought_process": "1. URL Check: Root code has no annotations -> Skip strict URL check (PASS). 2. Expectation Check: Code has 'logger.info', but scenario validation misses it -> FAIL (Feedback required).",
  "decision": "PASS" | "FAIL",
  "score": <0-100>,
  "feedback": "Specific feedback (Required if score < 100). e.g., 'Code contains logs, so expected result must include them.' (If code has no logs/returns, mark as 'PASS' with no feedback)"
}}
"""
)
