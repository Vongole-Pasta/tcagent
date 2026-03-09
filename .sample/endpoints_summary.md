# .sample API 엔드포인트 목록 (상세 구조체 포함)

이 문서는 `.sample/src` 소스코드의 Controller 클래스들과 `.sample/docs` 문서를 분석하여 통합된 엔드포인트 정보를 담고 있습니다. 각 항목에는 컨트롤러 코드 스니펫, 연관 하위 메서드 호출, API 규격서의 핵심 내용이 추가되었습니다.

---

## 1. 회원 (MemberController, `/api/members`)

### 1.a POST `/api/members` (createMember)
**상세내용**: 회원 생성 엔드포인트. 인증이 불필요하며, 성공 시 201 Created 객체를 리턴합니다.
- **엣지케이스**: `ResponseEntity<ApiResponse<MemberResponse>>` 형태의 중첩 제네릭 래핑이 있어서 파서가 실제 JSON 형태(code, message, data, meta)를 추론하기 어렵습니다.

**코드 스니펫**:
```java
@PostMapping
public ResponseEntity<ApiResponse<MemberResponse>> createMember(
        @Valid @RequestBody MemberCreateRequest request) {
    MemberResponse response = memberService.createMember(request);
    return ResponseEntity
            .status(HttpStatus.CREATED)
            .body(ApiResponse.success(ApiResponseCode.CREATED, response));
}
```
**하위 연관 메서드**:
- `memberService.createMember(request)`

**API 규격 요약**:
- **Request (application/json)**: `email`, `firstName`, `lastName`, `password`, `addresses`
- **Response (201 Created)**: `code`, `message`, `data` (생성된 회원 정보 - `id`, `email`, `fullName` 등), `meta`

### 1.b GET `/api/members/{id:[0-9]+}` (getMember)
**상세내용**: 특정 회원의 단건 조회입니다.
- **엣지케이스**: `PathVariable`에 정규식(`/{id:[0-9]+}`)이 적용되어 있어 비숫자 경로는 이 핸들러에 매핑 자체가 되지 않습니다.

**코드 스니펫**:
```java
@GetMapping("/{id:[0-9]+}")
public ResponseEntity<ApiResponse<MemberResponse>> getMember(
        @PathVariable Long id) {
    return ResponseEntity.ok(ApiResponse.success(memberService.getMember(id)));
}
```
**하위 연관 메서드**:
- `memberService.getMember(id)`

**API 규격 요약**:
- **Request (Path Variable)**: `id` (Long, 숫자만 허용)
- **Response (200 OK)**: `code`, `message`, `data` (회원 정보), `meta`

### 1.c GET `/api/members` (listMembers)
**상세내용**: 페이징된 회원 목록을 조회합니다.
- **엣지케이스**: 파라미터로 `Pageable` 객체를 직접 사용합니다. Spring이 쿼리 파라미터(`page`, `size`, `sort`)를 자동으로 바인딩하지만, 파서는 내부 구조를 알 수 없습니다.

**코드 스니펫**:
```java
@GetMapping
public ResponseEntity<ApiResponse<PagedResponse<MemberResponse>>> listMembers(
        Pageable pageable) {
    return ResponseEntity.ok(ApiResponse.success(memberService.findMembers(pageable)));
}
```
**하위 연관 메서드**:
- `memberService.findMembers(pageable)`

**API 규격 요약**:
- **Request (Query)**: `page` (int), `size` (int), `sort` (String)
- **Response (200 OK)**: `code`, `data` (`content` 리스트, `page`, `size`, `totalElements`, `totalPages`), `meta`

### 1.d GET, POST `/api/members/search` (searchMembers)
**상세내용**: 키워드를 이용한 회원 검색입니다. GET과 POST HTTP 메서드를 동시에 지원합니다.
- **엣지케이스**: `@RequestMapping(method = {RequestMethod.GET, RequestMethod.POST})` 처럼 배열 방식의 http_method 설정입니다.

**코드 스니펫**:
```java
@RequestMapping(value = "/search", method = {RequestMethod.GET, RequestMethod.POST})
public ResponseEntity<ApiResponse<List<MemberResponse>>> searchMembers(
        @RequestParam(required = false) String keyword) {
    return ResponseEntity.ok(ApiResponse.success(memberService.searchMembers(keyword)));
}
```
**하위 연관 메서드**:
- `memberService.searchMembers(keyword)`

**API 규격 요약**:
- **Request (Query)**: `keyword` (String, 선택)
- **Response (200 OK)**: `code`, `data` (검색된 회원 리스트), `meta`

### 1.e POST `/api/members/{id}/profile-image` (uploadProfileImage)
**상세내용**: 회원의 프로필 이미지를 업로드합니다.
- **엣지케이스**: 파라미터 타입이 `MultipartFile`이고 `consumes`가 업로드 형태로 제한되어 있습니다.

**코드 스니펫**:
```java
@PostMapping(value = "/{id}/profile-image", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
public ResponseEntity<ApiResponse<String>> uploadProfileImage(
        @PathVariable Long id,
        @RequestParam("file") MultipartFile file) {
    String url = memberService.uploadProfileImage(id, file);
    return ResponseEntity.ok(ApiResponse.success(url));
}
```
**하위 연관 메서드**:
- `memberService.uploadProfileImage(id, file)`

**API 규격 요약**:
- **Request (multipart/form-data)**: `id` (Path), `file` (MultipartFile)
- **Response (200 OK)**: `code`, `data` (업로드된 이미지의 URL), `meta`

### 1.f PUT `/api/members/{id}/address` (updateAddress)
**상세내용**: 회원의 주소 정보를 폼 데이터를 통해 수정합니다.
- **엣지케이스**: JSON 본문 대신 `@ModelAttribute`를 사용하여 폼 데이터(`application/x-www-form-urlencoded`)를 바인딩합니다.

**코드 스니펫**:
```java
@PutMapping("/{id}/address")
public ResponseEntity<ApiResponse<MemberResponse>> updateAddress(
        @PathVariable Long id,
        @ModelAttribute Address address) {
    return ResponseEntity.ok(ApiResponse.success(memberService.updateAddress(id, address)));
}
```
**하위 연관 메서드**:
- `memberService.updateAddress(id, address)`

**API 규격 요약**:
- **Request (URL Encoded Form)**: `id` (Path), `street`, `city`, `zipCode` (Form)
- **Response (200 OK)**: `code`, `data` (수정된 회원 정보), `meta`

### 1.g GET `/api/members/me` (getCurrentMember)
**상세내용**: 현재 인증된 회원의 정보를 조회합니다.
- **엣지케이스**: 데이터 소스가 쿠키(`@CookieValue`)와 헤더(`@RequestHeader`)에서 바인딩됩니다.

**코드 스니펫**:
```java
@GetMapping("/me")
public ResponseEntity<ApiResponse<MemberResponse>> getCurrentMember(
        @CookieValue(name = "SESSION_ID", required = false) String sessionId,
        @RequestHeader("X-Auth-Token") String authToken) {
    return ResponseEntity.ok(ApiResponse.success(memberService.getByToken(authToken)));
}
```
**하위 연관 메서드**:
- `memberService.getByToken(authToken)`

**API 규격 요약**:
- **Request**: `SESSION_ID` (Cookie), `X-Auth-Token` (Header)
- **Response (200 OK)**: `code`, `data` (회원 정보), `meta`

### 1.h GET `/api/members/audit` (getAuditLog)
**상세내용**: 감사 로그를 기록합니다. 성공 시 빈 응답을 줍니다.
- **엣지케이스**: 서블릿 API(`HttpServletRequest`, `HttpServletResponse`)에 직접 접근하며 리턴이 `void`입니다.

**코드 스니펫**:
```java
@GetMapping("/audit")
public void getAuditLog(
        HttpServletRequest request,
        HttpServletResponse response) {
    memberService.writeAuditLog(request, response);
}
```
**하위 연관 메서드**:
- `memberService.writeAuditLog(request, response)`

**API 규격 요약**:
- **Request**: 파라미터 없음
- **Response (200 OK)**: 본문 없음(void), 응답 헤더에 의존

---

## 2. 인증 (AuthController, `/api/auth`)

### 2.a POST `/api/auth/login` (login)
**상세내용**: JWT 토큰 발급 및 세션 생성을 통한 듀얼 인증 처리를 합니다.
- **엣지케이스**: 내부의 `authenticationManager.authenticate` 위임 호출과 `SecurityContextHolder` 관리가 수동으로 이루어집니다. 파서가 Spring Security 체인을 파악하기 어렵습니다.

**코드 스니펫**:
```java
@PostMapping("/login")
public ResponseEntity<ApiResponse<TokenResponse>> login(
        @Valid @RequestBody LoginRequest request,
        HttpServletRequest httpRequest) {
    // Spring Security 인증 수행
    Authentication authentication = authenticationManager.authenticate(
            new UsernamePasswordAuthenticationToken(request.email(), request.password())
    );
    SecurityContextHolder.getContext().setAuthentication(authentication);

    // 세션 활용
    HttpSession session = httpRequest.getSession(true);
    session.setAttribute("SPRING_SECURITY_CONTEXT", SecurityContextHolder.getContext());

    // 토큰 생성 및 반환 생략
    return ResponseEntity.ok(ApiResponse.success(TokenResponse.of(token, jwtExpiration)));
}
```
**하위 연관 메서드**:
- `authenticationManager.authenticate(Token)`
- `memberRepository.findByEmail(...)`
- `jwtTokenProvider.generateToken(...)`

**API 규격 요약**:
- **Request (application/json)**: `email`, `password`
- **Response (200 OK)**: `code`, `data` (`accessToken`, `tokenType`, `expiresIn`), `meta`

### 2.b POST `/api/auth/logout` (logout)
**상세내용**: 인증 세션을 무효화합니다.
- **엣지케이스**: `HttpServletRequest`를 받아 `Session` 객체를 강제로 초기화하고 빈 본문(Void) 응답을 반환합니다.

**코드 스니펫**:
```java
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
**API 규격 요약**:
- **Request**: 헤더 토큰 필요
- **Response (200 OK)**: 빈 응답

---

## 3. 상품 (ProductController, `/api/v1/products`)

### 3.a GET `/api/v1/products/{id}` (getProduct)
**상세내용**: 단건의 상품 상세정보를 조회합니다. URL(/v1/) 기반의 API 버저닝 형태입니다.

**코드 스니펫**:
```java
@GetMapping("/{id}")
public ResponseEntity<ApiResponse<ProductDto.Response>> getProduct(
        @PathVariable Long id) {
    return ResponseEntity.ok(ApiResponse.success(productService.getProduct(id)));
}
```
**하위 연관 메서드**:
- `productService.getProduct(id)`

**API 규격 요약**:
- **Request (Path)**: `id` (Long)
- **Response (200 OK)**: `code`, `data` (상품 상세), `meta`

### 3.b POST `/api/v1/products` (createProduct)
**상세내용**: 신규 상품을 생성합니다.
- **엣지케이스**: `@RequestBody`가 `ProductDto.Create` 라는 내부 중첩 `static class`를 참조합니다.

**코드 스니펫**:
```java
@PostMapping
public ResponseEntity<ApiResponse<ProductDto.Response>> createProduct(
        @Valid @RequestBody ProductDto.Create request) {
    return ResponseEntity
            .status(HttpStatus.CREATED)
            .body(ApiResponse.success(productService.createProduct(request)));
}
```
**하위 연관 메서드**:
- `productService.createProduct(request)`

**API 규격 요약**:
- **Request (application/json)**: `name`, `price`, `description`, `categoryId`, `stockQuantity`
- **Response (201 Created)**: 생성된 상품 응답

### 3.c PUT `/api/v1/products/{id}` (updateProduct)
**상세내용**: 상품 정보를 수정합니다. 매개변수로 내부 스태틱 클래스 `ProductDto.Update` 객체를 받습니다.

**코드 스니펫**:
```java
@PutMapping("/{id}")
public ResponseEntity<ApiResponse<ProductDto.Response>> updateProduct(
        @PathVariable Long id,
        @Valid @RequestBody ProductDto.Update request) {
    return ResponseEntity.ok(ApiResponse.success(productService.updateProduct(id, request)));
}
```
**하위 연관 메서드**:
- `productService.updateProduct(id, request)`

**API 규격 요약**:
- **Request (application/json)**: `id`(Path), 상품 수정 데이터(name 등)
- **Response (200 OK)**: 수정된 상품 응답

### 3.d GET `/api/v1/products/filter/{criteria}` (filterProducts)
**상세내용**: 매트릭스 변수를 통해 다중 속성 검색(예: `/filter/attrs;color=red;size=L`)을 지원합니다.
- **엣지케이스**: 특수한 `@MatrixVariable Map<String, String>` 바인딩.

**코드 스니펫**:
```java
@GetMapping("/filter/{criteria}")
public ResponseEntity<ApiResponse<List<ProductDto.Response>>> filterProducts(
        @MatrixVariable Map<String, String> criteria) {
    return ResponseEntity.ok(ApiResponse.success(productService.filterProducts(criteria)));
}
```
**하위 연관 메서드**:
- `productService.filterProducts(criteria)`

**API 규격 요약**:
- **Request (Matrix Path)**: `criteria` (Map 형태, `;key=value`)
- **Response (200 OK)**: 매칭된 상품의 `List`

### 3.e GET `/api/v1/products/async/{id}` (getProductAsync)
**상세내용**: `CompletableFuture`를 이용한 비동기식 상품 조회 핸들러입니다.
- **엣지케이스**: 삼중 제네릭 래핑(`CompletableFuture<ResponseEntity<ApiResponse<T>>>`)입니다.

**코드 스니펫**:
```java
@GetMapping("/async/{id}")
public CompletableFuture<ResponseEntity<ApiResponse<ProductDto.Response>>> getProductAsync(
        @PathVariable Long id) {
    return CompletableFuture.supplyAsync(() ->
            ResponseEntity.ok(ApiResponse.success(productService.getProduct(id)))
    );
}
```
**하위 연관 메서드**:
- `productService.getProduct(id)`

**API 규격 요약**:
- **Request (Path)**: `id` (Long)
- **Response (200 OK)**: 사실상 동기와 완전히 동일한 JSON 응답 반환

### 3.f GET `/api/v1/products/deferred/{id}` (getProductDeferred)
**상세내용**: `DeferredResult`를 이용한 비동기식 상품 조회 핸들러입니다.
- **엣지케이스**: 스프링 전용 `DeferredResult` 래퍼. 내부적으로 예외나 리절트를 수동으로 세팅합니다.

**코드 스니펫**:
```java
@GetMapping("/deferred/{id}")
public DeferredResult<ResponseEntity<ApiResponse<ProductDto.Response>>> getProductDeferred(
        @PathVariable Long id) {
    DeferredResult<ResponseEntity<ApiResponse<ProductDto.Response>>> result = new DeferredResult<>(5000L);
    CompletableFuture.supplyAsync(() -> productService.getProduct(id))
            .thenAccept(product -> result.setResult(ResponseEntity.ok(ApiResponse.success(product))))
            // exception 체이닝...
    return result;
}
```
**하위 연관 메서드**:
- `productService.getProduct(id)`

**API 규격 요약**:
- (비동기 처리 특성상 응답 자체는 3.a, 3.e와 동일합니다)

### 3.g DELETE `/api/v1/products/{id}` (deleteProduct)
**상세내용**: 특정 아이디의 상품을 삭제합니다.

**코드 스니펫**:
```java
@DeleteMapping("/{id}")
public ResponseEntity<Void> deleteProduct(@PathVariable Long id) {
    productService.deleteProduct(id);
    return ResponseEntity.noContent().build();
}
```
**하위 연관 메서드**:
- `productService.deleteProduct(id)`

**API 규격 요약**:
- **Request (Path)**: `id` (Long)
- **Response (204 No Content)**: 응답 Body 없음

---

## 4. 상품 검색 (ProductSearchController, `/api/products/search`)

### 4.a GET `/api/products/search` (searchV1) - 헤더 v1
**상세내용**: 전체 상품을 검색 후 리스트 형태로 단숨에 반환합니다. 
- **엣지케이스**: `headers = "X-Api-Version=1"` 헤더 밸류 기준의 버저닝 라우팅.

**코드 스니펫**:
```java
@GetMapping(headers = "X-Api-Version=1")
public ResponseEntity<ApiResponse<List<ProductDto.Response>>> searchV1(
        @RequestParam String q) {
    return ResponseEntity.ok(ApiResponse.success(productService.search(q)));
}
```
**하위 연관 메서드**:
- `productService.search(q)`

**API 규격 요약**:
- **Request**: `q` (Query), `X-Api-Version: 1` (Header)
- **Response (200 OK)**: List 데이터 형태 응답

### 4.b GET `/api/products/search` (searchV2) - 헤더 v2
**상세내용**: 전체 상품을 검색 후 `Pageable` 설정 기반의 페이징 형태로 반환합니다.
- **엣지케이스**: 같은 URI 임에도 헤더 `X-Api-Version=2` 값에 의해 v1(List 반환)과 다른 메서드로 분기됩니다.

**코드 스니펫**:
```java
@GetMapping(headers = "X-Api-Version=2")
public ResponseEntity<ApiResponse<PagedResponse<ProductDto.Response>>> searchV2(
        @RequestParam String q,
        Pageable pageable) {
    return ResponseEntity.ok(ApiResponse.success(productService.searchPaged(q, pageable)));
}
```
**하위 연관 메서드**:
- `productService.searchPaged(q, pageable)`

**API 규격 요약**:
- **Request**: `q`, `page`, `size` (Query), `X-Api-Version: 2` (Header)
- **Response (200 OK)**: 페이징 데이터 포맷 (`content`, `totalPages` 등)

### 4.c GET `/api/products/search/{id}/links` (getProductWithLinks)
**상세내용**: HATEOAS 기능으로 특정 상품의 데이터 구조와 사용 가능한 하이퍼미디어 링크(`_links`)를 반환합니다.

**코드 스니펫**:
```java
@GetMapping("/{id}/links")
public EntityModel<ProductDto.Response> getProductWithLinks(
        @PathVariable Long id) {
    ProductDto.Response product = productService.getProduct(id);
    return EntityModel.of(product,
            WebMvcLinkBuilder.linkTo(WebMvcLinkBuilder.methodOn(ProductSearchController.class).getProductWithLinks(id)).withSelfRel(),
            WebMvcLinkBuilder.linkTo(WebMvcLinkBuilder.methodOn(ProductController.class).getProduct(id)).withRel("product")
    );
}
```
**하위 연관 메서드**:
- `productService.getProduct(id)`
- Spring MVC `WebMvcLinkBuilder` 체인 연산

**API 규격 요약**:
- **Request (Path)**: `id`
- **Response (200 OK)**: 실제 정보 필드와 함께 `_links` (self, product) 블록이 섞여 자동 추가됨

---

## 5. 주문 (OrderController, `/api/orders`)

### 5.a POST `/api/orders` (createOrder)
**상세내용**: 회원이 장바구니 품목을 바탕으로 주문을 생성합니다.
- **엣지케이스**: `OrderCreateRequest` DTO 자체가 여러 Record 타입 객체(`OrderItemRequest`, `Address` 등)를 하위로 품고 있는 중첩 레코드입니다.

**코드 스니펫**:
```java
@PostMapping
public ResponseEntity<ApiResponse<OrderResponse>> createOrder(
        @Valid @RequestBody OrderCreateRequest request) {
    return ResponseEntity
            .status(HttpStatus.CREATED)
            .body(ApiResponse.success(orderService.createOrder(request)));
}
```
**하위 연관 메서드**:
- `orderService.createOrder(request)`

**API 규격 요약**:
- **Request (application/json)**: `memberId`, `items` (productId, quantity 리스트), `recipientName`, `phone`, `deliveryAddress` 중첩
- **Response (201 Created)**: 주문 요약 상태, 품목의 수량 및 단가, 총금액 반환

### 5.b GET `/api/orders/{id}` (getOrder)
**상세내용**: 생성된 주문의 내역을 단건 조회합니다.

**코드 스니펫**:
```java
@GetMapping("/{id}")
public ResponseEntity<ApiResponse<OrderResponse>> getOrder(
        @PathVariable Long id) {
    return ResponseEntity.ok(ApiResponse.success(orderService.getOrder(id)));
}
```
**하위 연관 메서드**:
- `orderService.getOrder(id)`

**API 규격 요약**:
- (5.a의 Response 형태와 동일한 주문 정보 JSON 반환)

### 5.c PATCH `/api/orders/{id}/status` (updateStatus)
**상세내용**: 단건 주문 상태를 변경합니다.
- **엣지케이스**: 쿼리스트링 문자열이 `OrderStatus` 이늄 타입에 자동 바인딩(Type Conversion)되며, 규칙은 핸들러 시그니처가 아닌 Enum 내부 구조에 정의되어 있습니다.

**코드 스니펫**:
```java
@PatchMapping("/{id}/status")
public ResponseEntity<ApiResponse<OrderResponse>> updateStatus(
        @PathVariable Long id,
        @RequestParam OrderStatus status) {
    return ResponseEntity.ok(ApiResponse.success(orderService.updateStatus(id, status)));
}
```
**하위 연관 메서드**:
- `orderService.updateStatus(id, status)`

**API 규격 요약**:
- **Request**: `id` (Path), `status` (Query - PENDING, CONFIRMED 등)
- **Response (200 OK)**: 상태가 변경된 주문 정보

### 5.d GET `/api/orders/reactive/{id}` (getOrderReactive)
**상세내용**: `Mono`를 사용해 단건 조회를 리액티브하게 서비스합니다.
- **엣지케이스**: 실제 응답 바디는 동기 호출과 같지만, 컨트롤러 상의 리턴 래퍼만 Reactor(`Mono`) 인프라입니다.

**코드 스니펫**:
```java
@GetMapping("/reactive/{id}")
public Mono<ResponseEntity<ApiResponse<OrderResponse>>> getOrderReactive(
        @PathVariable Long id) {
    return Mono.fromCallable(() -> orderService.getOrder(id))
            .map(r -> ResponseEntity.ok(ApiResponse.success(r)));
}
```
**하위 연관 메서드**:
- `orderService.getOrder(id)`

**API 규격 요약**:
- (응답 내용은 일반 단건 조회와 동일한 단발성 JSON입니다)

### 5.e GET `/api/orders/stream` (streamOrders)
**상세내용**: 실시간 주문 현황 스트림을 제공합니다 (`text/event-stream`).
- **엣지케이스**: `Flux` 반환값과 `TEXT_EVENT_STREAM_VALUE`가 조합된 SSE 푸시 파이프라인. 응답이 1회가 아님을 명시합니다.

**코드 스니펫**:
```java
@GetMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
public Flux<OrderResponse> streamOrders() {
    return orderService.streamRecentOrders();
}
```
**하위 연관 메서드**:
- `orderService.streamRecentOrders()`

**API 규격 요약**:
- **Request**: 파라미터 없음
- **Response (200 OK, text/event-stream)**: 계속 유지되는 커넥션으로 주문 발생 시점마다 `data: {...주문JSON}` 통신

### 5.f GET `/api/orders/my` (getMyOrders)
**상세내용**: 로그인 세션 정보(`X-Member-Id` 헤더 기반 권한)로부터 "내 주문기록" 목록을 노출합니다.
- **엣지케이스**: `@CurrentMember` 라는 독자적 Argument Resolver 어노테이션을 파라미터로 도입했습니다.

**코드 스니펫**:
```java
@GetMapping("/my")
public ResponseEntity<ApiResponse<List<OrderResponse>>> getMyOrders(
        @CurrentMember Long memberId) {
    return ResponseEntity.ok(ApiResponse.success(orderService.getByMember(memberId)));
}
```
**하위 연관 메서드**:
- `orderService.getByMember(memberId)`
- (Background 과정) `CurrentMemberArgumentResolver.resolveArgument()`

**API 규격 요약**:
- **Request**: `X-Member-Id` (Header, 백엔드 리졸버가 가져옴)
- **Response (200 OK)**: 내가 주문했던 모든 주문 형태의 `List` 응답

### 5.g GET `/api/orders/{id}/invoice` (downloadInvoice)
**상세내용**: 주문 번호를 토대로 영수증/인보이스 등을 PDF로 브라우저에 다운로드하게 합니다.
- **엣지케이스**: 리턴은 `byte[]`이며 `ContentType`이 PDF이고 `Content-Disposition=attachment` 헤더가 수동으로 추가됩니다.

**코드 스니펫**:
```java
@GetMapping(value = "/{id}/invoice", produces = MediaType.APPLICATION_PDF_VALUE)
public ResponseEntity<byte[]> downloadInvoice(@PathVariable Long id) {
    byte[] pdf = orderService.generateInvoice(id);
    return ResponseEntity.ok()
            .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=invoice-" + id + ".pdf")
            .body(pdf);
}
```
**하위 연관 메서드**:
- `orderService.generateInvoice(id)`

**API 규격 요약**:
- **Request (Path)**: `id`
- **Response (200 OK)**: 파일 바이너리 스트림 (JSON 아님)

---

## 6. 알림 (NotificationController, `/api/notifications`)

### 6.a GET `/api/notifications/subscribe` (subscribe)
**상세내용**: 멤버 ID에 맞는 특정 채널을 섭스크라이브하여 SSE 스트림 갱신을 받습니다.
- **엣지케이스**: Flux 같은 리액티브가 아니라, 전통적인 Spring MVC의 `SseEmitter`를 활용한 이벤트 스트리밍 방식.

**코드 스니펫**:
```java
@GetMapping(value = "/subscribe", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
public SseEmitter subscribe(@RequestParam Long memberId) {
    return notificationService.createEmitter(memberId);
}
```
**하위 연관 메서드**:
- `notificationService.createEmitter(memberId)`

**API 규격 요약**:
- **Request**: `memberId` (Query Param)
- **Response (200 OK)**: SSE 연결을 맺고 `event:notification`, `data:xxx` 형태의 이벤트 전송

### 6.b POST `/api/notifications/send` (sendNotification)
**상세내용**: 대규모 프로모션을 알리기 위해 특정 회원들에게 실시간 알림을 일괄 전송합니다. 본문 없이 빈 응답(HTTP 200)을 제공합니다.

**코드 스니펫**:
```java
@PostMapping("/send")
public ResponseEntity<Void> sendNotification(@RequestBody NotificationRequest request) {
    notificationService.sendBulk(request.memberIds(), request.message());
    return ResponseEntity.ok().build();
}
```
**하위 연관 메서드**:
- `notificationService.sendBulk(request.memberIds(), request.message())`

**API 규격 요약**:
- **Request (application/json)**: `memberIds` (배열), `message` (문자열)
- **Response (200 OK)**: 빈 응답
