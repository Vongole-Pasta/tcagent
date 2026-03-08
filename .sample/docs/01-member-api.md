# 회원(Member) API — 엣지케이스 가이드

> MemberController: 8개 엔드포인트
> 클래스 레벨: `@RequestMapping(value = "/api/members", produces = "application/json")`

---

## 1. 회원 생성

```
POST /api/members
Content-Type: application/json
```

```bash
# permitAll — 인증 불필요
curl -X POST http://localhost:8080/api/members \
  -H "Content-Type: application/json" \
  -H "X-Api-Version: 1" \
  -d '{
    "email": "new@example.com",
    "firstName": "신규",
    "lastName": "박",
    "password": "pass123",
    "addresses": [
      { "street": "강남대로 1", "city": "서울", "zipCode": "06000" }
    ]
  }'
```

**Request Body**
```json
{
  "email": "new@example.com",
  "firstName": "신규",
  "lastName": "박",
  "password": "pass123",
  "addresses": [
    { "street": "강남대로 1", "city": "서울", "zipCode": "06000" }
  ]
}
```

**Response (201 Created)**
```json
{
  "code": "CREATED",
  "message": "생성됨",
  "data": {
    "id": 100,
    "email": "new@example.com",
    "fullName": "신규 박",
    "grade": "BRONZE",
    "tags": [],
    "active": true
  },
  "meta": { "timestamp": 1709884800000, "traceId": "a1b2c3d4" }
}
```

**엣지케이스: ResponseEntity 중첩 래핑**

```java
// MemberController.java:63-70
@PostMapping
public ResponseEntity<ApiResponse<MemberResponse>> createMember(
        @Valid @RequestBody MemberCreateRequest request) {
    MemberResponse response = memberService.createMember(request);
    return ResponseEntity
            .status(HttpStatus.CREATED)
            .body(ApiResponse.success(ApiResponseCode.CREATED, response));
}
```

- 파서가 추출하는 리턴타입 layout: `["ResponseEntity", "ApiResponse", "MemberResponse"]`
- **실제 응답 구조를 알려면** `ApiResponse<T>` 클래스를 열어봐야 code/message/data/meta 필드를 알 수 있음
- HTTP 상태코드 `201`은 코드 내부의 `HttpStatus.CREATED`에서 결정 → 파서가 추출하지 못함

---

## 2. 회원 단건 조회

```
GET /api/members/{id}    ← id는 숫자만 허용 (정규식)
```

```bash
# 정상 — 숫자 ID (인증 필요)
curl http://localhost:8080/api/members/1 \
  -H "X-Api-Version: 1" \
  -H "Authorization: Bearer <token>"

# 실패 — 문자 ID → 핸들러 매핑 자체가 안 됨 (500 반환)
curl http://localhost:8080/api/members/abc \
  -H "X-Api-Version: 1" \
  -H "Authorization: Bearer <token>"
```

**Request**
| 파라미터 | 위치 | 타입 | 설명 |
|---|---|---|---|
| `id` | Path | Long | 회원 ID (숫자만 허용) |

**Response (200 OK)**
```json
{
  "code": "SUCCESS",
  "message": "성공",
  "data": {
    "id": 1,
    "email": "hong@example.com",
    "fullName": "길동 홍",
    "grade": "BRONZE",
    "tags": [],
    "active": true
  },
  "meta": { "timestamp": 1709884800000, "traceId": "e5f6g7h8" }
}
```

**엣지케이스: 정규식 PathVariable**

```java
// MemberController.java:78-82
@GetMapping("/{id:[0-9]+}")
public ResponseEntity<ApiResponse<MemberResponse>> getMember(
        @PathVariable Long id) {
    return ResponseEntity.ok(ApiResponse.success(memberService.getMember(id)));
}
```

- `/{id:[0-9]+}` — 정규식이 경로에 포함
- 파서가 URI를 `/{id:[0-9]+}`로 추출하지만, 정규식 부분의 의미(숫자만 허용)를 해석하지 못함
- 비숫자 경로는 **이 핸들러에 매핑 자체가 되지 않음** → 별도 에러 핸들링 필요

---

## 3. 회원 목록 조회 (페이징)

```
GET /api/members?page=0&size=10&sort=email,asc
```

```bash
# 인증 필요
curl "http://localhost:8080/api/members?page=0&size=10&sort=email,asc" \
  -H "X-Api-Version: 1" \
  -H "Authorization: Bearer <token>"
```

**Request**
| 파라미터 | 위치 | 타입 | 설명 |
|---|---|---|---|
| `page` | Query | int | 페이지 번호 (0부터 시작) |
| `size` | Query | int | 페이지 크기 |
| `sort` | Query | String | 정렬 기준 (예: `email,asc`) |

**Response (200 OK)**
```json
{
  "code": "SUCCESS",
  "data": {
    "content": [ { "id": 1, "email": "hong@example.com", ... }, ... ],
    "page": 0,
    "size": 10,
    "totalElements": 3,
    "totalPages": 1
  },
  "meta": { ... }
}
```

**엣지케이스: Pageable 파라미터**

```java
// MemberController.java:91-95
@GetMapping
public ResponseEntity<ApiResponse<PagedResponse<MemberResponse>>> listMembers(
        Pageable pageable) {
    return ResponseEntity.ok(ApiResponse.success(memberService.findMembers(pageable)));
}
```

- `Pageable pageable` — 어노테이션 없음
- Spring이 `page`, `size`, `sort` 쿼리 파라미터를 자동으로 Pageable 객체에 바인딩
- 파서는 `Pageable` 타입만 보이고, 실제로 어떤 쿼리 파라미터가 필요한지 알 수 없음
- `@RequestParam`이 아니므로 파서의 파라미터 어노테이션 추출에도 잡히지 않음

---

## 4. 회원 검색 (GET + POST 복수 메서드)

```
GET  /api/members/search?keyword=홍
POST /api/members/search?keyword=홍
```

```bash
# GET으로 검색 (한글은 URL-encode 필요, 인증 필요)
curl "http://localhost:8080/api/members/search?keyword=%ED%99%8D" \
  -H "X-Api-Version: 1" \
  -H "Authorization: Bearer <token>"

# POST로도 동일하게 동작
curl -X POST "http://localhost:8080/api/members/search?keyword=%ED%99%8D" \
  -H "X-Api-Version: 1" \
  -H "Authorization: Bearer <token>"
```

**Request**
| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| `keyword` | Query | String | N | 검색 키워드 (없으면 전체 조회) |

**Response (200 OK)**
```json
{
  "code": "SUCCESS",
  "data": [ { "id": 1, "email": "hong@example.com", ... } ],
  "meta": { ... }
}
```

**엣지케이스: 하나의 핸들러에 복수 HTTP 메서드**

```java
// MemberController.java:104-108
@RequestMapping(value = "/search", method = {RequestMethod.GET, RequestMethod.POST})
public ResponseEntity<ApiResponse<List<MemberResponse>>> searchMembers(
        @RequestParam(required = false) String keyword) {
    return ResponseEntity.ok(ApiResponse.success(memberService.searchMembers(keyword)));
}
```

- `method = {RequestMethod.GET, RequestMethod.POST}` — 배열로 복수 HTTP 메서드 지정
- 파서가 `http_method`를 추출할 때 배열을 어떻게 처리하는지가 관건
- 실제 파싱 결과: `"POST}"` — 닫는 괄호가 포함되는 버그 발생

---

## 5. 프로필 이미지 업로드

```
POST /api/members/{id}/profile-image
Content-Type: multipart/form-data
```

```bash
# 인증 필요
curl -X POST http://localhost:8080/api/members/1/profile-image \
  -H "X-Api-Version: 1" \
  -H "Authorization: Bearer <token>" \
  -F "file=@/path/to/photo.jpg"
```

**Request**
| 파라미터 | 위치 | 타입 | 설명 |
|---|---|---|---|
| `id` | Path | Long | 회원 ID |
| `file` | Multipart | MultipartFile | 업로드할 이미지 파일 |

**Response (200 OK)**
```json
{
  "code": "SUCCESS",
  "data": "/uploads/profile/1/photo.jpg",
  "meta": { ... }
}
```

**엣지케이스: MultipartFile + consumes 지정**

```java
// MemberController.java:117-123
@PostMapping(value = "/{id}/profile-image", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
public ResponseEntity<ApiResponse<String>> uploadProfileImage(
        @PathVariable Long id,
        @RequestParam("file") MultipartFile file) {
    String url = memberService.uploadProfileImage(id, file);
    return ResponseEntity.ok(ApiResponse.success(url));
}
```

- `consumes = MediaType.MULTIPART_FORM_DATA_VALUE` — Content-Type 제한
- 파서가 `consumes` 속성을 추출하지 못함 → JSON 엔드포인트와 구분 불가
- `MultipartFile`은 Spring 전용 타입이므로 파서가 파일 업로드 엔드포인트임을 인지할 수 없음

---

## 6. 주소 수정 (폼 데이터)

```
PUT /api/members/{id}/address
Content-Type: application/x-www-form-urlencoded
```

```bash
# 인증 필요
curl -X PUT http://localhost:8080/api/members/1/address \
  -H "X-Api-Version: 1" \
  -H "Authorization: Bearer <token>" \
  -d "street=테헤란로 427" \
  -d "city=서울" \
  -d "zipCode=06159"
```

**Request (Form Data)**
| 파라미터 | 위치 | 타입 | 설명 |
|---|---|---|---|
| `id` | Path | Long | 회원 ID |
| `street` | Form | String | 도로명 주소 |
| `city` | Form | String | 도시 |
| `zipCode` | Form | String | 우편번호 |

**Response (200 OK)**
```json
{
  "code": "SUCCESS",
  "data": { "id": 1, "email": "hong@example.com", ... },
  "meta": { ... }
}
```

**엣지케이스: @ModelAttribute (폼 바인딩)**

```java
// MemberController.java:132-137
@PutMapping("/{id}/address")
public ResponseEntity<ApiResponse<MemberResponse>> updateAddress(
        @PathVariable Long id,
        @ModelAttribute Address address) {
    return ResponseEntity.ok(ApiResponse.success(memberService.updateAddress(id, address)));
}
```

- `@ModelAttribute` — `@RequestBody`가 아닌 폼 데이터 바인딩
- JSON이 아닌 `application/x-www-form-urlencoded` 또는 `multipart/form-data`로 전달
- 파서는 `@ModelAttribute`를 파라미터 어노테이션으로 캡처하지만,
  이것이 "JSON Body가 아닌 폼 데이터"라는 의미를 해석하지 못함
- 같은 `Address` 타입이어도 `@RequestBody`와 `@ModelAttribute`는 전혀 다른 바인딩 방식

---

## 7. 현재 회원 조회 (쿠키 + 헤더 바인딩)

```
GET /api/members/me
Cookie: SESSION_ID=session-abc
X-Auth-Token: 1
```

```bash
# 인증 필요
curl http://localhost:8080/api/members/me \
  -H "X-Api-Version: 1" \
  -H "Authorization: Bearer <token>" \
  -H "X-Auth-Token: 1" \
  -b "SESSION_ID=session-abc"
```

**Request**
| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| `SESSION_ID` | Cookie | String | N | 세션 ID |
| `X-Auth-Token` | Header | String | Y | 인증 토큰 (회원 ID 값) |

**Response (200 OK)**
```json
{
  "code": "SUCCESS",
  "data": { "id": 1, "email": "hong@example.com", "fullName": "길동 홍", "grade": "BRONZE", ... },
  "meta": { ... }
}
```

**엣지케이스: @CookieValue + @RequestHeader**

```java
// MemberController.java:146-151
@GetMapping("/me")
public ResponseEntity<ApiResponse<MemberResponse>> getCurrentMember(
        @CookieValue(name = "SESSION_ID", required = false) String sessionId,
        @RequestHeader("X-Auth-Token") String authToken) {
    return ResponseEntity.ok(ApiResponse.success(memberService.getByToken(authToken)));
}
```

- 이 파라미터들은 URL이나 Body가 아닌 **HTTP 헤더/쿠키**에서 값을 추출
- 파서는 어노테이션 텍스트를 캡처하지만, "이 값은 쿠키에서 온다" / "이 값은 헤더에서 온다"라는
  의미를 해석하지 못함 → API 문서 자동 생성 시 입력 소스를 구분할 수 없음

---

## 8. 감사 로그 (Servlet API 직접 접근)

```
GET /api/members/audit
```

```bash
# 인증 필요
curl http://localhost:8080/api/members/audit \
  -H "X-Api-Version: 1" \
  -H "Authorization: Bearer <token>"
```

**Request**: 없음 (파라미터 없이 호출)

**Response (200 OK)**: 본문 없음 (void), `X-Audit-Logged: true` 헤더만 설정

**엣지케이스: HttpServletRequest/Response 직접 사용**

```java
// MemberController.java:160-165
@GetMapping("/audit")
public void getAuditLog(
        HttpServletRequest request,
        HttpServletResponse response) {
    memberService.writeAuditLog(request, response);
}
```

- 리턴 타입: `void`
- 파서가 파라미터 타입(`HttpServletRequest`, `HttpServletResponse`)은 추출하지만:
  - 이것이 Spring이 주입하는 서블릿 컨텍스트 객체라는 것을 알 수 없음
  - 응답이 `response` 객체에 직접 쓰여지므로 리턴 타입(`void`)만으로는 응답 형태를 알 수 없음
  - 어떤 헤더가 설정되는지, 상태코드가 어떻게 결정되는지 컨트롤러 시그니처만으로 판단 불가

---

## 공통: 컨트롤러 밖에서 일어나는 일들

위 모든 엔드포인트에 대해 **파서가 볼 수 없는** 처리가 일어남:

### Spring Security 인증 (v2 추가)

`POST /api/members`(회원 가입)를 제외한 모든 Member API 엔드포인트는 JWT 인증이 필요합니다.

```bash
# 1. 로그인해서 JWT 토큰 획득
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"hong@example.com","password":"password123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['accessToken'])")

# 2. 인증 헤더를 붙여서 API 호출
curl http://localhost:8080/api/members/1 \
  -H "X-Api-Version: 1" \
  -H "Authorization: Bearer $TOKEN"
```

- 인증 없이 보호 경로 접근 시 **401 Unauthorized** (응답 본문 없음)
- `SecurityConfig.filterChain()`에서 인가 규칙 정의 → 컨트롤러 코드에 드러나지 않음
- `JwtAuthenticationFilter`가 `Authorization: Bearer <token>` 헤더를 추출하여 인증 → 필터 체인은 파서가 추적 불가
- 자세한 인증 흐름은 [05-auth-api.md](05-auth-api.md) 참조

### 인터셉터 (ApiVersionInterceptor)

```java
// ApiVersionInterceptor.java:24-43
@Override
public boolean preHandle(HttpServletRequest request, HttpServletResponse response,
                         Object handler) throws Exception {
    String uri = request.getRequestURI();
    if (uri.matches("/api/v\\d+/.*")) {
        return true;  // URL 버전 API는 통과
    }
    String version = request.getHeader("X-Api-Version");
    if (version == null || version.isBlank()) {
        response.setStatus(HttpStatus.BAD_REQUEST.value());
        response.getWriter().write("{\"error\": \"X-Api-Version header is required\"}");
        return false;
    }
    return true;
}
```

- `/api/v1/**`, `/api/v2/**`가 아닌 경로에서는 `X-Api-Version` 헤더 필수
- 헤더가 없으면 **컨트롤러에 도달하기 전에** 400 Bad Request 반환
- → 컨트롤러 코드만 보면 이 검증이 있는지 알 수 없음

### 필터 (RequestLoggingFilter)
- 모든 요청의 HTTP 메서드, URI, 상태코드, 처리시간을 로깅
- → 컨트롤러와 무관하게 동작하므로 파서가 감지 불가

### 전역 예외 처리 (GlobalExceptionHandler)

```java
// GlobalExceptionHandler.java:31-37
@ExceptionHandler(BusinessException.class)
public ResponseEntity<ApiResponse<Void>> handleBusinessException(BusinessException e) {
    ErrorCode errorCode = e.getErrorCode();
    return ResponseEntity
            .status(errorCode.getHttpStatus())
            .body(ApiResponse.error(ApiResponseCode.BAD_REQUEST, errorCode.getMessage()));
}
```

모든 에러 응답은 컨트롤러가 아닌 여기서 결정됨:

```json
// BusinessException 발생 시 (예: 회원 없음)
{
  "code": "BAD_REQUEST",
  "message": "회원을 찾을 수 없습니다",
  "data": null,
  "meta": { ... }
}

// @Valid 검증 실패 시 (예: email 누락)
{
  "code": "BAD_REQUEST",
  "message": "{email=must not be blank}",
  "data": null,
  "meta": { ... }
}

// 인증 실패 시 (v2 추가)
// → 401 Unauthorized, 응답 본문 없음 (HttpStatusEntryPoint)

// 잘못된 자격 증명 시 (v2 추가)
{
  "code": "BAD_REQUEST",
  "message": "이메일 또는 비밀번호가 올바르지 않습니다",
  "data": null,
  "meta": { ... }
}
```

→ 컨트롤러의 리턴 타입만으로는 에러 시 응답 형태를 추론할 수 없음
→ v2에서 추가된 Security 예외(BadCredentialsException, AccessDeniedException)도 동일하게 GlobalExceptionHandler에서 처리됨
