from langchain_core.prompts import PromptTemplate, ChatPromptTemplate

# 프롬프트 버전 관리 — 변경 시 버전을 올려 LangSmith 트레이스에서 추적 가능
PROMPT_VERSION = "v3.0"

PAYLOAD_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", 
"""역할: 수석 백엔드 엔지니어.
목표: Spring Controller 메서드를 분석하고 클라이언트(프론트엔드/API 소비자)가 명시적으로 전송해야 하는 데이터만 추출합니다.

**지시사항**:
1. **입력 파라미터 분석**: 제공된 루트 메서드(Root Method) 코드와 DB의 원시 파라미터를 분석합니다.
2. **내부 파라미터 제외**:
   - 프레임워크 주입 객체(`HttpServletRequest`, `HttpServletResponse`, `Model`, `Principal`, `Authentication` 등)는 반드시 제외합니다.
   - 서버 내부 속성(`@RequestAttribute`, `@LoginUser` 등)은 반드시 제외합니다.
3. **클라이언트 페이로드 식별**:
   - `@RequestBody` DTO (주요 JSON 바디를 구성함)는 반드시 포함합니다.
   - `@RequestParam` 또는 `@ModelAttribute` (쿼리 스트링 또는 폼 데이터)는 반드시 포함합니다.
   - `@PathVariable` (URL 경로 변수)는 반드시 포함합니다.
4. **필수 헤더 식별**:
   - 명시적인 `@RequestHeader` 파라미터가 있는지 확인합니다.
   - API가 본질적으로 인증을 요구하는지 확인합니다 (예: `Principal`이나 사용자 신원과 관련된 `@RequestAttribute`가 있다면 `Authorization: Bearer <TOKEN>` 헤더가 필요할 가능성이 높음).
   - 식별된 항목들을 `required_headers` 목록에 추가합니다.

**출력 형식**:
{format_instructions}
"""),
    ("user", 
"""**루트 메서드 코드 (Root Method Code)**: 
{root_method_code}

**원시 파라미터 내역 DB (Raw Parameters)**:
{raw_parameters}""")
])

SCENARIO_GENERATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", 
"""역할: 수석 API 테스트 엔지니어.
목표: 변경된 코드의 **특정 로직**을 검증하기 위해 바로 실행 가능한 `curl` 명령어(또는 내부 절차)를 생성합니다.

**지시사항**:
1. **추출된 페이로드 및 헤더 분석**: 클라이언트가 전송해야 하는 `Payload Schema`와 인증 또는 사용자 정의 헤더인 `Required Headers`가 제공됩니다.
2. **로직 (대상) 분석**: `Target Method`의 특정 로직을 트리거하기 위해 필요한 **특정 값**을 식별합니다. (예: 대상이 `status == "VOID"`를 확인하는 경우 입력 JSON에서 이 값이 통과되도록 해야 합니다).
3. **시나리오 생성**:
   - 변경된 로직에 여러 분기가 있는 경우 **여러 개**의 시나리오를 생성합니다.
   - 변경 사항을 실행하는 **유효한 요청 (성공 경로)**에 집중합니다.
4. **실행 단계 생성**:
   - **REST API의 경우 (`@RequestMapping` 등이 있는 경우)**:
     - `procedure` 필드에 유효하고 실행 가능한 `curl` 명령어를 생성합니다.
     - 반드시 `-H 'Content-Type: application/json'`을 사용해야 합니다.
     - **중요**: `Required Headers` 입력에 나열된 모든 헤더를 반드시 포함해야 합니다. (예: `-H 'Authorization: Bearer <TOKEN>'`).
     - **페이로드 전략**: 제공된 `Payload Schema`를 JSON 구조로 사용하고, `Target Method`를 트리거하는 값으로 채웁니다.
   - **내부 메서드의 경우 (HTTP 어노테이션이 없는 경우)**:
     - `curl` 명령어를 생성하지 마십시오.
     - `procedure` 필드에 메서드를 프로그래밍 방식으로 호출하는 방법을 설명하십시오 (예: "`WrapperDto.getData()` 호출").
     - `api_endpoint` 필드를 `"INTERNAL"`로 설정하십시오.
5. **내부 DTO/Entity 처리 (중요)**:
   - `Input Context`에 HTTP 요청 매핑이나 상위 컨트롤러 없이 단순한 Getter/Setter, 생성자 또는 순수 데이터 처리 메서드와 같은 단순 내부 메서드만 포함된 경우:
     - 존재하지 않는 상위 호출자(예: `WrapperService`, `NoteManager`)를 지어내거나 환각(hallucinate)하지 마십시오.
     - 단지 기본 단위 테스트 스타일의 절차만 생성하십시오 (예: "객체를 생성하고 `.getData()`를 호출한다").
     - `api_endpoint` 필드를 `"INTERNAL_DTO_ONLY"`로 설정하십시오.
6. **언어**: 식별자, 설명, 전제 조건, 절차 및 예상 결과에는 반드시 **한국어**를 사용하십시오.

**출력 형식**:
{format_instructions}
**핵심 주의사항**: 반드시 유효한 JSON 배열(Array) 하나만 반환해야 합니다. 마크다운 블록, 부연 설명, 사과 문구 등은 절대 포함하지 마십시오.
**핵심 주의사항**: 제공된 입력 컨텍스트에 대해 최소 한 개(1) 이상의 시나리오를 반드시 생성해야 합니다. 빈 배열 `[]`을 반환하는 것은 엄격히 금지됩니다.

다음은 원하는 출력 구조의 예시입니다 (Few-Shot Learning).
**참고**: 아래 예시는 **구조 참조용**으로만 사용하십시오.
- `api_endpoint`: 추출된 HTTP 메서드 및 URL (예: "POST /api/v1/users"). API가 아닌 경우 "INTERNAL" 또는 "INTERNAL_DTO_ONLY"를 사용합니다.
- **예상 결과**: 검증할 특정 로직에 기반해야 합니다.
   - **좋은 예**: "JSON {{'status':'error'}}를 반환하고 '유효하지 않은 ID' 에러 로그를 출력한다."
   - **나쁜 예**: "요청이 성공한다." 또는 "200 OK를 반환한다."

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
"""**입력 컨텍스트(Input Context)**:
1. **루트 메서드 (진입점)**: {root_method}
   - **중요**: 코드/어노테이션을 분석하여 **HTTP Method**와 **URL**을 추출하십시오 (예: `@PostMapping("/api/test")` -> `POST /api/test`).
2. **페이로드 스키마 (클라이언트 데이터)**: {payload_schema}
   - **JSON BODY/QUERY에 활용**: 클라이언트가 전송해야 하는 필터링된 순수 데이터입니다. 이 스키마에 없는 파라미터는 지어내지 마십시오.
3. **요구되는 헤더**: {required_headers}
   - **CURL 헤더에 활용**: 이 값들을 curl 명령어 안에 강제로 `-H` 옵션으로 주입하십시오.
4. **대상 메서드 (변경된 로직)**: {validation_context}
   - **값 생성에 활용**: 변경되어 검증이 필요한 특정 로직입니다.
   - **중요**: 생성된 요청은 이 특정 로직의 분기를 반드시 타도록 실행되어야 합니다.
5. **피드백 (참고용)**: {feedback} / **이전 결과**: {previous_scenarios}""")
])

TEST_STRATEGY_PROMPT = PromptTemplate(
    input_variables=["target_summary", "trace_summary"],
    template="""
역할: QA 리드 매니저.
목표: 변경 사항을 기반으로 명확하고 간결한 테스트 전략 요약 보고서를 작성합니다.

**입력 데이터**:
- 대상 요약 (Targets): {target_summary}
- 진입점 요약 (Entry Points): {trace_summary}

**보고서 구조 (마크다운 형식)**:
### 1. 변경점 요약 (Changes)
- 주요 로직 변경 사항을 간결하게 요약합니다.

### 2. 영향도 분석 (Impact Analysis)
- 영향을 받는 모든 API 엔드포인트를 포괄적으로 목록화합니다.

### 3. 주요 테스트 포인트 (Key Test Points)
- 핵심 검증 항목들을 명시합니다 (**강조**할 키워드에는 볼드체 사용).
"""
)

SCENARIO_EVALUATION_PROMPT = PromptTemplate(
    input_variables=["validation_context", "scenarios", "format_instructions"],
    template="""
역할: 수석 보안/품질 감사관 (조건부 엄격한 검증).
언어: 항상 한국어로 출력할 것 (특히 피드백 메시지).
작업: 제공된 소스 코드를 바탕으로 생성된 테스트 시나리오가 **사실에 기반하여 정확한지** 검증합니다.

**평가 기준 (중요: 코드가 단순하다면 유연하게 평가할 것)**:

1. **절차 검증 (URL 및 HTTP 메서드)**:
   - **루트 메서드 코드 검토**: `@RequestMapping`, `@PostMapping`, `@GetMapping` 또는 유사한 REST 어노테이션이 있는지 확인합니다.
   - **REST API (어노테이션 있음)**: 생성된 `curl` 명령어는 이 어노테이션의 경로와 메서드(POST/GET 등)와 정확히 일치해야 합니다. (불일치하거나 curl이 없으면 **FAIL**).
   - **내부 메서드 (어노테이션 없음)**: 이것은 HTTP 엔드포인트가 아닙니다. 
     - `curl` 명령어가 없다고 해서 감점하지 마십시오.
     - HTTP 상태 코드(예: 200 OK)가 없다고 해서 감점하지 마십시오.
     - 시나리오가 HTTP 요청 대신 적절한 단위 테스트 스타일의 절차(예: "특정 파라미터로 메서드를 호출한다")를 설명하고 있다면 **PASS** 시키십시오.

2. **예상 결과 검증 (로그 및 반환값)**:
   - **소스 코드 검토**: 코드 내에 `logger.info(...)`, `return ...`, 또는 `throw ...` 구문이 존재합니까?
   - **예 (아티팩트 존재)**: "예상 결과"에는 이 명시적인 로그 문구나 반환값이 반드시 언급되어야 합니다. (모호하면 **FAIL**).
   - **아니오 (Void/로그 없음)**: 파라미터 처리가 전부이거나 화면 구동이 없는 경우, 단순한 성공 메시지(예: "성공적으로 실행됨")에 대해 실패를 주지 마십시오. 코드가 외부에 가시적인 동작을 하지 않는다면 기초적인 성공 예상도 허용됩니다.

3. **로직 연관성 검증**:
   - 입력 페이로드가 **대상 메서드(Target Method)**의 특정 로직 분기나 필수 파라미터 대역을 정확히 조준하여 발생/트리거하도록 설계되어 있습니까?

**출력 형식**:
{format_instructions}
**핵심 주의사항**: 여러 개의 시나리오를 평가하더라도 개별 객체의 배열을 반환하지 말고, 모든 시나리오를 총합하여 단 하나의 단일 JSON 객체 규칙으로 반환하십시오. 여러 개 중 하나라도 잘못되었다면 가장 낮은 점수와 실패 결정을 내리십시오.
**핵심 주의사항**: 반환하는 JSON의 `feedback` 필드는 반드시 처음부터 끝까지 한국어(Korean)로만 작성되어야 합니다.

**입력 컨텍스트(Input Context)**:
{validation_context}

**검증할 시나리오 목록(Scenarios)**:
{scenarios}
"""
)

