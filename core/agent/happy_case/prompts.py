HAPPY_CASE_GENERATOR_PROMPT = """
당신은 백엔드 개발자이자 QA 엔지니어입니다. 제공된 코드 문맥을 분석하여 해당 API의 **Happy Case (성공 케이스, 200 OK)** 테스트 데이터를 생성해 주세요.

[대상 엔드포인트]
- URL: {endpoint_url}
- Method: {http_method}
- Name: {name}

[비즈니스 로직 문맥]
{methods_context}

[API DTO 구조 (필수 준수)]
{dto_context}

[DTO 매핑 및 호출 지침]
- **중요**: `expected_result` (응답 바디)에는 오직 **[API DTO 구조]**에 정의된 필드만 포함해야 합니다.
- **입력 데이터(input_data) 생성 지침**:
  - 엔드포인트 메서드의 파라미터 목록(`params`)을 보고 각 데이터의 소스를 판단하세요.
  - **Body**: DTO 타입이거나 `@RequestBody`인 경우 JSON 바디로 작성하세요.
  - **Header**: `@RequestHeader` 또는 이름/타입상 헤더로 추정되는 경우, `input_data` 최상단에 "Header: Key=Value" 형식으로 작성하세요.
  - **Path**: `@PathVariable` 또는 URL 패턴(`{id}` 등)과 일치하는 경우, "Path: Key=Value" 형식으로 작성하세요.
  - **Query**: `@RequestParam` 또는 기타 원시 타입인 경우, "Query: Key=Value" 형식으로 작성하세요.
  - 여러 소스가 섞여 있다면 각각 명시한 후 마지막에 바디 JSON을 작성하세요.
- **예상 결과(expected_result) 생성 지침**:
  - `Content-Type: application/json`과 같이 당연한 정보는 생략하세요.
  - `Location` 헤더(리소스 생성 시)나 `Set-Cookie` 등 **비즈니스적으로 의미 있는 특정 응답 헤더**가 코드상에서 확인될 경우에만, JSON 바디 앞에 "Header: Key=Value" 형식으로 명시하세요.
- **보안/토큰**: `token`이나 `Authorization`과 같은 보안 정보는 헤더로 명시하되, 실제 값이 아닌 `<TOKEN>`과 같은 플레이스홀더를 사용하세요.

[요구사항]
1. 반드시 200 OK(또는 생성 시 201 Created)가 발생하는 성공 시나리오만 작성하세요.
2. `test_case`: "OOO 기능을 보장하기 위해 유효한 데이터를 전송함"과 같이 해당 API의 기능 위주로 한국어로 설명하세요.
3. `input_data`: API 호출에 필요한 입력 데이터 JSON을 작성하세요.
4. `expected_result`: 성공 시 예상되는 응답 데이터를 작성하세요. (의미 있는 헤더가 있다면 JSON 위에 명시)
"""
