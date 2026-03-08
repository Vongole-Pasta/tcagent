# 인증(Auth) API — 엣지케이스 가이드

> AuthController: 2개 엔드포인트 (`/api/auth`)

---

## 1. 로그인

```
POST /api/auth/login
Content-Type: application/json
```

```bash
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "hong@example.com",
    "password": "password123"
  }'
```

**Request Body**
```json
{
  "email": "hong@example.com",
  "password": "password123"
}
```

**Response (200 OK)**
```json
{
  "code": "SUCCESS",
  "message": "성공",
  "data": {
    "accessToken": "eyJhbGciOiJIUzUxMiJ9...",
    "tokenType": "Bearer",
    "expiresIn": 3600000
  },
  "meta": { "timestamp": 1709884800000, "traceId": "a1b2c3d4" }
}
```

**로그인 실패 시 (400)**
```json
{
  "code": "BAD_REQUEST",
  "message": "이메일 또는 비밀번호가 올바르지 않습니다",
  "data": null,
  "meta": { ... }
}
```

**엣지케이스: AuthenticationManager + 듀얼 인증**

```java
// AuthController.java:54-92
@PostMapping("/login")
public ResponseEntity<ApiResponse<TokenResponse>> login(
        @Valid @RequestBody LoginRequest request,
        HttpServletRequest httpRequest) {
    // Spring Security 인증 처리
    Authentication authentication = authenticationManager.authenticate(
            new UsernamePasswordAuthenticationToken(request.email(), request.password()));
    SecurityContextHolder.getContext().setAuthentication(authentication);

    // 세션 생성 (Session 기반 인증용)
    HttpSession session = httpRequest.getSession(true);
    session.setAttribute("SPRING_SECURITY_CONTEXT", SecurityContextHolder.getContext());

    // JWT 토큰 생성
    String token = jwtTokenProvider.generateToken(request.email(), member.getGrade().name());
    return ResponseEntity.ok(ApiResponse.success(TokenResponse.of(token, jwtExpiration)));
}
```

- `AuthenticationManager.authenticate()` — Spring Security의 인증 위임 체인
- `new UsernamePasswordAuthenticationToken(...)` — 생성자 호출을 파서가 일반 메서드로 처리
- JWT + Session 듀얼 인증: 로그인 시 JWT 토큰 반환과 동시에 세션 생성
- `@Value("${jwt.expiration}")` — 프로퍼티 바인딩을 파서가 감지하지 못함
- `HttpServletRequest` 파라미터 — 세션 생성을 위해 서블릿 컨텍스트 직접 접근
- 파서 관점 한계:
  - `authenticationManager` 필드의 타입이 인터페이스(`AuthenticationManager`) → 실제 구현체 추적 불가
  - 인증 실패 시 `BadCredentialsException` → `GlobalExceptionHandler`에서 처리되므로 컨트롤러만으로 에러 응답 추론 불가

---

## 2. 로그아웃

```
POST /api/auth/logout
```

```bash
curl -X POST http://localhost:8080/api/auth/logout \
  -H "Authorization: Bearer <token>"
```

**Request**: 없음 (인증 헤더만 필요)

**Response (200 OK)**: 본문 없음 (빈 200 응답)

**엣지케이스: 세션 무효화 + SecurityContext 정리**

```java
// AuthController.java:97-105
@PostMapping("/logout")
public ResponseEntity<Void> logout(HttpServletRequest request) {
    HttpSession session = request.getSession(false);
    if (session != null) {
        session.invalidate();
    }
    SecurityContextHolder.clearContext();
    return ResponseEntity.ok().build();
}
```

- 리턴 타입: `ResponseEntity<Void>` — 빈 응답
- `HttpServletRequest` 파라미터로 세션 접근 → 파서는 이것이 인증 관련 처리라는 것을 알 수 없음
- 세션 무효화 + SecurityContext 정리는 메서드 본문에만 있어 시그니처로 파악 불가

---

## 공통: 인증 흐름

### JWT 인증 (우선)
```
요청 → JwtAuthenticationFilter → Bearer 토큰 추출 → JwtTokenProvider.validateToken()
      → SecurityContext에 인증 정보 설정 → 컨트롤러 도달
```

### Session 인증 (폴백)
```
요청 → JSESSIONID 쿠키 → Spring Session 관리 → SecurityContext 복원 → 컨트롤러 도달
```

### 인증 필요 경로 vs permitAll 경로

| 경로 | 인증 | 비고 |
|---|---|---|
| `POST /api/auth/login` | 불필요 | 로그인 |
| `POST /api/members` | 불필요 | 회원 가입 |
| `GET /api/v1/products/**` | 불필요 | 상품 조회 |
| `GET /api/products/search/**` | 불필요 | 상품 검색 |
| `GET /api/orders/stream` | 불필요 | SSE 스트림 |
| `/api/notifications/**` | 불필요 | 알림 |
| `/h2-console/**` | 불필요 | DB 콘솔 |
| 그 외 모든 경로 | **필요** | `Authorization: Bearer <token>` |

### 파서가 감지할 수 없는 인증 처리 체인

```
SecurityConfig.filterChain()
  → JwtAuthenticationFilter (extends OncePerRequestFilter)
    → JwtTokenProvider.validateToken() / getUsernameFromToken()
      → CustomUserDetailsService.loadUserByUsername()
        → MemberRepository.findByEmail()
```

- 이 전체 체인은 **컨트롤러 코드에 나타나지 않음**
- `SecurityConfig`의 `@Bean` 메서드와 필터 등록은 파서가 DI 관계로 추적 불가
- `extends OncePerRequestFilter`, `implements UserDetailsService` — 상속/구현 관계 미감지
