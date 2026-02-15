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
- **Do NOT hallucinate** values that cannot be inferred from the provided Context.
- If a value is unknown, use a placeholder (e.g., `{{user_id}}`) or a reasonable default based on type.

```json
[
  {{
    "api_endpoint": "POST /V100/VMS_90002/drop_table",
    "test_case_name": "단기 영상테이블 삭제 (Example)",
    "step_no": 1,
    "description": "현재기준 longTableCycle 이전의 날짜의 테이블을 DROP한다.",
    "pre_condition": "config_properties.xml : vod.table.partition.long.yn 값이 'Y'",
    "procedure": "curl -X POST -H 'Content-Type:application/json' http://vms-vod:18080/V100/VMS_90002/drop_table? -d '{{\"user_id\":\"9999999999\",\"cam_id\":\"D99999999999999\",\"user_cam_code\":\"999999999\"}}'",
    "expected_result": "HTTP 200 OK 응답과 함께 테이블이 삭제되어야 한다."
  }},
  {{
    "api_endpoint": "POST /V100/VMS_45001/recorded_video_url",
    "test_case_name": "녹화영상 조회 (Example)",
    "step_no": 1,
    "description": "단기 영상데이터를 조회한다.",
    "pre_condition": "config_properties.xml : vod.table.partition.long.yn 값이 'N'",
    "procedure": "curl -X POST http://10.10.10.10:18080/V100/VMS_45001/recorded_video_url -H 'Content-Type: application/json' -d '{{\"user_id\": \"P_USER_ID\", \"secure_yn\": \"Y\", \"cam_info\": [{{\"cam_id\": \"P_CAM_ID\", \"playlist_yn\": \"N\", \"search_datetime_info\": [{{\"start_time\": \"20230626000000\", \"end_time\": \"20230626235959\"}}]}}]}}'",
    "expected_result": "{{\"res_msg\":\"성공\",\"data\":{{\"list\":[...]}}}}"
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
- List affected API endpoints.

### 3. 주요 테스트 포인트 (Key Test Points)
- List critical verification items (**Bold** keywords).
"""
)

SCENARIO_EVALUATION_PROMPT = PromptTemplate(
    input_variables=["scenarios", "validation_context"],
    template="""
Role: QA Lead Auditor.
Task: Evaluate if the test scenarios represent **Valid API Calls** that target the changed logic.

**Context**:
- Scenarios: {scenarios}
- Changed Code: {validation_context}

**Scoring Criteria**:
- **100 (Pass)**: The scenario constructs a **Valid API Request** (correct endpoint/structure) and attempts to verify the logic.
- **80-99 (Pass with feedback)**: Valid request, but the description or expected result is generic.
- **< 80 (Fail)**: The API call is invalid (wrong endpoint/method) or completely unrelated to the change.

**Evaluation Focus**:
1. **Interface Compliance**: Is the `curl` command compatible with the **Root Method**'s interface? (Endpoint, Method, JSON Structure).
2. **Intent Match**: Does the test case *intend* to verify the specific change? (e.g., using specific values mentioned in the code).
3. **Plausibility**: Is the expected result plausible for success?

**Instruction**:
- **IGNORE** internal logic reachability (you cannot know for sure).
- **FOCUS** on whether the Request is **Well-Formed** and **Relevant**.
- Give **100** if the curl looks correct and relevant.

**Output (JSON)**:
{{
  "thought_process": "Check Interface Compliance and Intent...",
  "decision": "PASS" (Score >= 80) or "FAIL",
  "score": <0-100>,
  "feedback": "Feedback in Korean (Required only if score < 100)."
}}
"""
)
