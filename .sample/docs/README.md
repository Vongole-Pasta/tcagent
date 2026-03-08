# 엣지케이스 가이드 — 사용 방법

이 문서는 **tcagent가 생성한 테스트 시나리오의 품질을 검증**하는 사람을 위한 가이드입니다.

---

## 이 문서의 목적

tcagent는 Java 소스코드를 파싱하고, 변경된 메서드를 기준으로 API 회귀 테스트 시나리오를 자동 생성합니다.
하지만 파서와 에이전트에는 한계가 있어, 특정 패턴의 코드에서 **부정확한 테스트가 생성**될 수 있습니다.

이 가이드는 ShopOne 샘플 프로젝트의 각 엔드포인트별로:
- 실제 요청/응답 형태 (curl, JSON)
- 해당 코드의 어떤 부분이 엣지케이스인지
- 파서/에이전트가 왜 틀릴 수 있는지

를 정리하여, 생성된 테스트 시나리오를 **어떤 기준으로 판단해야 하는지** 알려줍니다.

---

## 검증 흐름

### 1단계: 샘플 프로젝트 업로드

```bash
cd .sample
zip -r /tmp/shopone.zip src/main/java/ -x "*/test/*"

curl -X POST "http://localhost:8000/upload" \
  -F "files=@/tmp/shopone.zip" \
  -F "project=shopone"
```

### 2단계: 테스트 시나리오 생성

```bash
curl -X POST "http://localhost:8000/api/tests/generate"
```

### 3단계: 생성된 시나리오 검증

생성된 각 시나리오에 대해, 아래 체크리스트로 품질을 확인합니다.

---

## 검증 체크리스트

### A. curl 명령어가 정확한가?

| 확인 항목 | 올바른 예 | 흔한 오류 |
|---|---|---|
| HTTP 메서드 | `curl -X POST` | GET인데 POST로 생성 |
| URL 경로 | `/api/v1/products/{id}` | 클래스 레벨 prefix 누락 |
| Content-Type | `-H "Content-Type: multipart/form-data"` | multipart인데 JSON으로 생성 |
| 인증 헤더 | `-H "X-Member-Id: 1"` | 커스텀 헤더 누락 |
| API 버전 헤더 | `-H "X-Api-Version: 1"` | `/api/v1/` 외 경로에서 누락 시 400 |
| 쿠키 | `-b "SESSION_ID=abc"` | `@CookieValue` 무시 |

**참고할 엣지케이스 문서:**
- `consumes`/`produces` 미추출 → [01-member-api.md #5](01-member-api.md#5-프로필-이미지-업로드)
- 커스텀 ArgumentResolver → [03-order-api.md #6](03-order-api.md#6-내-주문-목록-조회-커스텀-argumentresolver)
- 쿠키/헤더 바인딩 → [01-member-api.md #7](01-member-api.md#7-현재-회원-조회-쿠키--헤더-바인딩)

### B. 요청 본문(JSON)이 정확한가?

| 확인 항목 | 올바른 예 | 흔한 오류 |
|---|---|---|
| DTO 필드명 | `"firstName": "길동"` | 존재하지 않는 필드 사용 |
| 중첩 객체 | `"items": [{"productId": 1}]` | 중첩 Record 구조 무시 |
| Enum 값 | `"status": "CONFIRMED"` | 유효하지 않은 Enum 값 |
| 폼 데이터 | `-d "street=강남대로"` | `@ModelAttribute`인데 JSON 사용 |

**참고할 엣지케이스 문서:**
- 중첩 Record → [03-order-api.md #1](03-order-api.md#1-주문-생성)
- 내부 static 클래스 DTO → [02-product-api.md #2](02-product-api.md#2-상품-생성)
- `@ModelAttribute` 폼 바인딩 → [01-member-api.md #6](01-member-api.md#6-주소-수정-폼-데이터)

### C. 기대 결과(expected_result)가 정확한가?

| 확인 항목 | 올바른 예 | 흔한 오류 |
|---|---|---|
| HTTP 상태코드 | `201 Created` | 항상 200으로 생성 |
| 응답 래핑 구조 | `{"code":"SUCCESS","data":{...}}` | `ApiResponse` 래핑 누락 |
| 빈 응답 | `200 OK, 본문 없음` | `ResponseEntity<Void>`인데 JSON 기대 |
| 바이너리 응답 | `application/pdf 파일` | `byte[]`인데 JSON 기대 |
| SSE 스트림 | `text/event-stream` | 스트리밍인데 단건 JSON 기대 |
| HATEOAS | `_links` 필드 포함 | `EntityModel` 래핑 무시 |

**참고할 엣지케이스 문서:**
- `ResponseEntity<Void>` → [04-notification-api.md #2](04-notification-api.md#2-알림-일괄-발송)
- PDF 다운로드 → [03-order-api.md #7](03-order-api.md#7-주문-인보이스-다운로드-pdf)
- SSE 스트림 → [03-order-api.md #5](03-order-api.md#5-최근-주문-실시간-스트림-sse), [04-notification-api.md #1](04-notification-api.md#1-sse-구독)
- HATEOAS → [02-product-api.md #10](02-product-api.md#10-상품-상세--hateoas-링크)

### D. 비즈니스 로직을 반영했는가?

| 확인 항목 | 올바른 예 | 흔한 오류 |
|---|---|---|
| 상태 전이 규칙 | `PENDING → CONFIRMED` 만 허용 | 아무 상태나 전이 시도 |
| 정규식 PathVariable | `/api/members/1` (숫자만) | `/api/members/abc` 로 테스트 |
| 소프트 삭제 | `deactivate()` 호출 검증 | 물리 삭제(DELETE)로 기대 |

**참고할 엣지케이스 문서:**
- 상태 전이 → [03-order-api.md #3](03-order-api.md#3-주문-상태-변경)
- 정규식 PathVariable → [01-member-api.md #2](01-member-api.md#2-회원-단건-조회)

---

## 엣지케이스 문서 목록

| 문서 | 엔드포인트 | 주요 엣지케이스 |
|---|---|---|
| [01-member-api.md](01-member-api.md) | 8개 | ResponseEntity 래핑, 정규식 PathVariable, Pageable, 복수 HTTP 메서드, MultipartFile, @ModelAttribute, @CookieValue/@RequestHeader, HttpServletRequest/Response |
| [02-product-api.md](02-product-api.md) | 9개 | URL 기반 API 버전, 내부 static 클래스 DTO, @MatrixVariable, CompletableFuture, DeferredResult, 헤더 기반 API 버전, HATEOAS |
| [03-order-api.md](03-order-api.md) | 7개 | 중첩 Record, Enum 바인딩, 상태 전이, Mono/Flux 리액티브, SSE 스트림, 커스텀 ArgumentResolver, PDF 다운로드 |
| [04-notification-api.md](04-notification-api.md) | 2개 | SseEmitter (Servlet SSE), ResponseEntity\<Void\> |

---

## 알려진 한계

아래 항목은 현재 파서/에이전트가 처리하지 못하는 영역입니다.
생성된 테스트에서 이 부분이 잘못되어 있다면, **에이전트의 문제가 아닌 알려진 한계**입니다.

1. **인터셉터/필터 전처리**: `ApiVersionInterceptor`가 헤더를 검증하지만, 에이전트가 이를 모름
2. **전역 예외 처리**: `GlobalExceptionHandler`의 에러 응답 형태를 에이전트가 추론할 수 없음
3. **`this.` 호출 추적 실패**: 메서드 내부에서 `this.validate()` 같은 자기 호출이 그래프에서 끊김
4. **Repository 기본 메서드**: `findById`, `save` 등 JPA 기본 메서드가 외부 호출로 분류됨
5. **동명 타입 충돌**: `ProductDto.Response`가 `Response`로 축약되어 다른 `Response`와 혼동
