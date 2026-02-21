from langchain_core.prompts import PromptTemplate, ChatPromptTemplate

# 프롬프트 버전 관리 — 변경 시 버전을 올려 LangSmith 트레이스에서 추적 가능
PROMPT_VERSION = "v3.0"

PAYLOAD_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", 
"""Role: Senior Backend Engineer.
Goal: Analyze a Spring Controller method and extract ONLY the data that the client (frontend/API consumer) must explicitly send.

**Instructions**:
1. **Analyze the Input Parameters**: You will be provided with the Root Method code and its raw parameters.
2. **Filter out Internal Parameters**:
   - MUST EXCLUDE: Framework-injected objects (e.g., `HttpServletRequest`, `HttpServletResponse`, `Model`, `Principal`, `Authentication`).
   - MUST EXCLUDE: Internal server-provided attributes (e.g., `@RequestAttribute`, `@LoginUser`).
3. **Identify Client Payload**:
   - MUST INCLUDE: `@RequestBody` DTOs (this forms the main JSON body).
   - MUST INCLUDE: `@RequestParam` or `@ModelAttribute` (query strings or form data).
   - MUST INCLUDE: `@PathVariable` (URL components).
4. **Identify Required Headers**:
   - Check if any explicit `@RequestHeader` parameters exist.
   - Check if the API intrinsically requires Authentication (e.g., if there is a `Principal` or `@RequestAttribute` related to user identity, chances are it requires an `Authorization: Bearer <TOKEN>` header).
   - Add these to the `required_headers` list.

**Output Format**:
{format_instructions}
"""),
    ("user", 
"""**Root Method Code**: 
{root_method_code}

**Raw Parameters (From DB)**:
{raw_parameters}""")
])

SCENARIO_GENERATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", 
"""Role: Senior API Testing Engineer.
Goal: Generate execution-ready `curl` commands to verify the **Specific Logic** in the Changed Code.

**Instructions**:
1. **Analyze Extracted Payload & Headers**: You are given the `Payload Schema` (what the client must send) and `Required Headers` (authentication or custom headers).
2. **Analyze Logic (Target)**: Identify the **Specific Values** required to trigger the `Target Method`'s logic. (e.g., if target checks `status == "VOID"`, input JSON must allow this value to pass).
3. **Generate Scenarios**:
   - Create **MULTIPLE** scenarios if the Changed Logic has distinct branches.
   - Focus on **Valid Requests (Happy Path)** that exercise the change.
4. **Generate Execution Steps**:
   - **For REST APIs (Has `@RequestMapping` etc.)**:
     - Generate a valid, executable `curl` command in the `procedure` field.
     - MUST use `-H 'Content-Type: application/json'`.
     - **CRITICAL**: You MUST include EVERY header listed in the `Required Headers` input. (e.g., `-H 'Authorization: Bearer <TOKEN>'`).
     - **Payload Strategy**: Use the provided `Payload Schema` for the JSON structure, and fill it with values that trigger the `Target Method`.
   - **For Internal Methods (No HTTP Annotations)**:
     - DO NOT generate a `curl` command.
     - In the `procedure` field, describe how to call the method programmatically (e.g., "Call `WrapperDto.getData()`").
     - Set the `api_endpoint` field to `"INTERNAL"`.
5. **Language**: Use **Korean** for Name, Description, Pre-condition, Procedure, and Expected Result.

**Output Format**:
{format_instructions}
**CRITICAL**: You MUST return ONLY a valid JSON array. Do not include markdown blocks, explanations, or apology messages.

Following is an example of the desired output structure (Few-Shot Learning).
**NOTE**: The examples below are for **Structure Reference ONLY**.
- `api_endpoint`: The extracted HTTP Method and URL (e.g., "POST /api/v1/users"). Use "INTERNAL" if not an API.
- **Expected Result**: MUST be specific logic-based.
   - **GOOD**: "Returns JSON {{'status':'error'}} AND logs 'Invalid ID' error."
   - **BAD**: "Request succeeds." or "Returns 200 OK."

```json
[
  {{
    "test_case_id": "TC-001",
    "test_case_name": "단기 영상테이블 삭제 (Example)",
    "step_no": 1,
    "description": "현재기준 longTableCycle 이전의 날짜의 테이블을 DROP한다.",
    "pre_condition": "config_properties.xml : vod.table.partition.long.yn 값이 'Y'",
    "procedure": "curl -X POST -H 'Content-Type:application/json' http://vms-vod:18080/V100/VMS_90002/drop_table? -d '{{\"user_id\":\"9999999999\",\"cam_id\":\"D99999999999999\",\"user_cam_code\":\"999999999\"}}'",
    "expected_result": "HTTP 200 OK 응답. 서버 로그에 'Drop table VMS_90002 success' 메시지가 출력되어야 함.",
    "scenario_id": "SC-001",
    "api_endpoint": "POST /V100/VMS_90002/drop_table"
  }}
]
```"""),
    ("user", 
"""**Input Context**:
1. **Root Method (Entry Point)**: {root_method}
   - **CRITICAL**: Analyze the code/annotations to extract the **HTTP Method** and **URL** (e.g., `@PostMapping("/api/test")` -> `POST /api/test`).
2. **Payload Schema (Client Data)**: {payload_schema}
   - **USE THIS FOR JSON BODY/QUERY**: This is the filtered, pure data the client must send. DO NOT add parameters that are not in this schema.
3. **Required Headers**: {required_headers}
   - **USE THIS FOR CURL HEADERS**: Inject these directly into your curl command as `-H` options.
4. **Target Method (Changed Logic)**: {validation_context}
   - **USE THIS FOR VALUES**: The specific logic that needs verification.
   - **CRITICAL**: The generated request MUST trigger this specific logic.
5. **Feedback**: {feedback} / **Previous**: {previous_scenarios}""")
])

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

SCENARIO_EVALUATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", 
"""Role: Lead Auditor (Conditional Strict Verification).
Language: Korean (for feedback).
Task: Verify if the generated test scenarios are **Factually Correct** based on the provided Source Code.

**Evaluation Criteria (IMPORTANT: Be Flexible if Code is simple)**:

1. **Procedure Verification (Url & Method)**:
   - **Review Root Method Code**: Check if it has `@RequestMapping`, `@PostMapping`, `@GetMapping` or similar REST annotations.
   - **REST API (Has Annotations)**: The `curl` command MUST match these annotations exactly. (**FAIL** if mismatch or missing curl).
   - **INTERNAL METHOD (No Annotations)**: This is NOT an HTTP endpoint. 
     - Do **NOT** penalize the absence of `curl`.
     - Do **NOT** penalize the absence of HTTP status codes (like 200 OK).
     - **PASS** the scenario if it describes a proper unit-test style procedure (e.g., "Call the method with specific parameters") instead of an HTTP request.

2. **Expected Result Verification (Logs & Returns)**:
   - **Review Source Code**: Does it contain `logger.info(...)`, `return ...`, or `throw ...` statements?
   - **YES (Artifacts Exist)**: The "Expected Result" MUST mention these specific logs or return values. (**FAIL** if vague).
   - **NO (Void/No Logs)**: Do **NOT** Fail for generic success messages (e.g., "HTTP 200 OK"). If the code does nothing visible, a simple success expectation is acceptable.

3. **Logic Relevance**:
   - Does the input payload appear to target the specific logic parameters in the **Target Method**?

**Output Format**:
{format_instructions}
**CRITICAL**: You MUST return a SINGLE JSON object evaluating ALL scenarios collectively. Do NOT return an array of objects. Provide the lowest score and worst decision if evaluating multiple scenarios.
"""),
    ("user", 
"""**Input Context**:
{validation_context}

**Scenarios to Verify**:
{scenarios}""")
])

