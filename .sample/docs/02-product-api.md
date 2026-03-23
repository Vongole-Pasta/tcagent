# 상품(Product) API — 엣지케이스 가이드

> ProductController: 6개 엔드포인트 (`/api/v1/products`)
> ProductSearchController: 3개 엔드포인트 (`/api/products/search`)

---

## 1. 상품 단건 조회

```
GET /api/v1/products/{id}
```

```bash
curl http://localhost:8080/api/v1/products/1
```

**Request**
| 파라미터 | 위치 | 타입 | 설명 |
|---|---|---|---|
| `id` | Path | Long | 상품 ID |

**Response (200 OK)**
```json
{
  "code": "SUCCESS",
  "data": {
    "id": 1,
    "name": "노트북",
    "price": 1500000,
    "description": "고성능 노트북",
    "categoryName": "전자기기",
    "stockQuantity": 10,
    "active": true
  },
  "meta": { "timestamp": 1709884800000, "traceId": "a1b2c3d4" }
}
```

**엣지케이스: URL 기반 API 버전**

```java
// ProductController.java:33
@RestController
@RequestMapping("/api/v1/products")
public class ProductController {
```

- 파서가 URI `/api/v1/products/{id}`를 추출하지만, `/v1/`이 API 버전이라는 의미를 알 수 없음
- 향후 `/api/v2/products/{id}`가 추가되어도 파서는 "같은 리소스의 다른 버전"이라는 관계를 파악 불가

---

## 2. 상품 생성

```
POST /api/v1/products
Content-Type: application/json
```

```bash
# 인증 필요 (GET은 permitAll이지만 POST는 인증 필요)
curl -X POST http://localhost:8080/api/v1/products \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "name": "무선 키보드",
    "price": 89000,
    "description": "블루투스 기계식 키보드",
    "categoryId": 1,
    "stockQuantity": 50
  }'
```

**Request Body**
```json
{
  "name": "무선 키보드",
  "price": 89000,
  "description": "블루투스 기계식 키보드",
  "categoryId": 1,
  "stockQuantity": 50
}
```

**Response (201 Created)**
```json
{
  "code": "SUCCESS",
  "data": {
    "id": 2,
    "name": "무선 키보드",
    "price": 89000,
    "description": "블루투스 기계식 키보드",
    "categoryName": "전자기기",
    "stockQuantity": 50,
    "active": true
  },
  "meta": { ... }
}
```

**엣지케이스: 내부 static 클래스를 Request Body로 사용**

```java
// ProductController.java:56-62
@PostMapping
public ResponseEntity<ApiResponse<ProductDto.Response>> createProduct(
        @Valid @RequestBody ProductDto.Create request) {
    return ResponseEntity
            .status(HttpStatus.CREATED)
            .body(ApiResponse.success(productService.createProduct(request)));
}
```

```java
// ProductDto.java — 하나의 파일에 여러 내부 클래스
public class ProductDto {
    public static class Create { ... }
    public static class Update { ... }
    public record Response(...) { ... }
}
```

- 파라미터 타입: `ProductDto.Create` — `ProductDto`의 내부 static 클래스
- 파서가 `ProductDto$Create`로 qualname을 추출하지만,
  다른 파일에도 `Create`라는 이름의 클래스가 있으면 **동명 타입 충돌** 발생 (마지막 등록만 유효)

---

## 3. 상품 수정

```
PUT /api/v1/products/{id}
Content-Type: application/json
```

```bash
# 인증 필요
curl -X PUT http://localhost:8080/api/v1/products/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{ "name": "노트북 Pro", "price": 1800000 }'
```

**Request Body**
```json
{
  "name": "노트북 Pro",
  "price": 1800000
}
```

**Response (200 OK)**: 상품 조회와 동일한 형태

---

## 4. 상품 필터링 (Matrix Variable)

```
GET /api/v1/products/filter/{criteria}
```

```bash
# 세미콜론으로 구분된 속성 필터
curl "http://localhost:8080/api/v1/products/filter/attrs;color=red;size=L"
```

**Request**
| 파라미터 | 위치 | 타입 | 설명 |
|---|---|---|---|
| `criteria` | Path (Matrix) | Map\<String, String\> | 세미콜론 구분 속성 필터 (예: `;color=red;size=L`) |

**Response (200 OK)**
```json
{
  "code": "SUCCESS",
  "data": [
    { "id": 3, "name": "빨간 티셔츠", ... }
  ],
  "meta": { ... }
}
```

**엣지케이스: @MatrixVariable**

```java
// ProductController.java:83-87
@GetMapping("/filter/{criteria}")
public ResponseEntity<ApiResponse<List<ProductDto.Response>>> filterProducts(
        @MatrixVariable Map<String, String> criteria) {
    return ResponseEntity.ok(ApiResponse.success(productService.filterProducts(criteria)));
}
```

- URL 경로에 `;key=value` 형태로 파라미터를 전달하는 방식 (RFC 3986)
- 일반적인 `?key=value` 쿼리 파라미터와 완전히 다른 바인딩 방식
- 파서가 `@MatrixVariable`을 어노테이션으로 캡처하지만:
  - 세미콜론 구분 파라미터라는 의미를 알 수 없음
  - `Map<String, String>`이 동적 키-값 쌍이라는 것을 알 수 없음
  - API 문서화 도구도 대부분 지원하지 않는 희귀한 바인딩 방식

---

## 5. 비동기 상품 조회 (CompletableFuture)

```
GET /api/v1/products/async/{id}
```

```bash
curl http://localhost:8080/api/v1/products/async/1
```

**Request**
| 파라미터 | 위치 | 타입 | 설명 |
|---|---|---|---|
| `id` | Path | Long | 상품 ID |

**Response (200 OK)**: 상품 조회와 동일한 JSON (비동기로 처리될 뿐)

**엣지케이스: CompletableFuture 래핑**

```java
// ProductController.java:96-102
@GetMapping("/async/{id}")
public CompletableFuture<ResponseEntity<ApiResponse<ProductDto.Response>>> getProductAsync(
        @PathVariable Long id) {
    return CompletableFuture.supplyAsync(() ->
            ResponseEntity.ok(ApiResponse.success(productService.getProduct(id)))
    );
}
```

- **3중 제네릭 중첩**: `CompletableFuture` > `ResponseEntity` > `ApiResponse` > `ProductDto.Response`
- 파서가 리턴 타입의 layout을 추출하면:
  `["CompletableFuture", "ResponseEntity", "ApiResponse", "Response"]`
- 실제 응답은 `ApiResponse<ProductDto.Response>` 인데,
  `CompletableFuture`와 `ResponseEntity`는 Spring 인프라 래퍼임을 알 수 없음
- 동기 엔드포인트(`GET /{id}`)와 응답이 동일하지만 리턴 타입이 완전히 다름

---

## 6. 비동기 상품 조회 (DeferredResult)

```
GET /api/v1/products/deferred/{id}
```

```bash
curl http://localhost:8080/api/v1/products/deferred/1
```

**Request**
| 파라미터 | 위치 | 타입 | 설명 |
|---|---|---|---|
| `id` | Path | Long | 상품 ID |

**Response (200 OK)**: 상품 조회와 동일

**엣지케이스: DeferredResult 래핑**

```java
// ProductController.java:110-125
@GetMapping("/deferred/{id}")
public DeferredResult<ResponseEntity<ApiResponse<ProductDto.Response>>> getProductDeferred(
        @PathVariable Long id) {
    DeferredResult<ResponseEntity<ApiResponse<ProductDto.Response>>> result =
            new DeferredResult<>(5000L);

    CompletableFuture.supplyAsync(() -> productService.getProduct(id))
            .thenAccept(product ->
                    result.setResult(ResponseEntity.ok(ApiResponse.success(product))))
            .exceptionally(ex -> {
                result.setErrorResult(ex);
                return null;
            });

    return result;
}
```

- `DeferredResult`는 Spring 전용 비동기 래퍼
- 응답이 `result.setResult(...)` 로 **비동기적으로** 설정됨
- 타임아웃(5000ms) 설정이 있지만 파서가 이를 알 수 없음
- 결과적으로 동기/CompletableFuture/DeferredResult 3개의 엔드포인트가
  **동일한 응답**을 반환하지만 파서는 이들을 서로 다른 API로 인식

---

## 7. 상품 삭제

```
DELETE /api/v1/products/{id}
```

```bash
# 인증 필요
curl -X DELETE http://localhost:8080/api/v1/products/1 \
  -H "Authorization: Bearer <token>"
```

**Request**
| 파라미터 | 위치 | 타입 | 설명 |
|---|---|---|---|
| `id` | Path | Long | 삭제할 상품 ID |

**Response (204 No Content)**: 응답 본문 없음

```java
// ProductController.java:131-135
@DeleteMapping("/{id}")
public ResponseEntity<Void> deleteProduct(@PathVariable Long id) {
    productService.deleteProduct(id);
    return ResponseEntity.noContent().build();
}
```

**비고**: 리턴 타입 `ResponseEntity<Void>` — 파서가 `Void`를 리턴 타입으로 추출하며,
실제로 본문이 없다는 것과 일치

---

## 8. 상품 검색 v1 (헤더 기반 API 버전)

```
GET /api/products/search?q=노트북
X-Api-Version: 1
```

```bash
curl "http://localhost:8080/api/products/search?q=%EB%85%B8%ED%8A%B8%EB%B6%81" \
  -H "X-Api-Version: 1"
```

**Request**
| 파라미터 | 위치 | 타입 | 설명 |
|---|---|---|---|
| `q` | Query | String | 검색 키워드 |
| `X-Api-Version` | Header | String | API 버전 (`1`) |

**Response (200 OK)**
```json
{
  "code": "SUCCESS",
  "data": [
    { "id": 1, "name": "노트북", "price": 1500000, ... }
  ],
  "meta": { ... }
}
```

**엣지케이스: 헤더 기반 API 버전 분기**

```java
// ProductSearchController.java:44-48
@GetMapping(headers = "X-Api-Version=1")
public ResponseEntity<ApiResponse<List<ProductDto.Response>>> searchV1(
        @RequestParam String q) {
    return ResponseEntity.ok(ApiResponse.success(productService.search(q)));
}
```

- `headers = "X-Api-Version=1"` — 헤더 값에 따라 다른 핸들러 매핑
- **같은 URL** `/api/products/search`에 대해 헤더 값에 따라 **다른 핸들러**가 매핑됨
- 파서가 `headers` 속성을 추출하지 못함 → v1과 v2가 같은 엔드포인트로 보임
- 리턴 타입도 다름: v1은 `List<ProductDto.Response>`, v2는 `PagedResponse<ProductDto.Response>`

---

## 9. 상품 검색 v2 (페이징)

```
GET /api/products/search?q=노트북&page=0&size=10
X-Api-Version: 2
```

```bash
curl "http://localhost:8080/api/products/search?q=%EB%85%B8%ED%8A%B8%EB%B6%81&page=0&size=10" \
  -H "X-Api-Version: 2"
```

**Request**
| 파라미터 | 위치 | 타입 | 설명 |
|---|---|---|---|
| `q` | Query | String | 검색 키워드 |
| `page` | Query | int | 페이지 번호 |
| `size` | Query | int | 페이지 크기 |
| `X-Api-Version` | Header | String | API 버전 (`2`) |

**Response (200 OK)**
```json
{
  "code": "SUCCESS",
  "data": {
    "content": [ { "id": 1, "name": "노트북", ... } ],
    "page": 0,
    "size": 10,
    "totalElements": 1,
    "totalPages": 1
  },
  "meta": { ... }
}
```

**엣지케이스**: 위 #8과 동일한 URL이지만 헤더 값으로 분기

```java
// ProductSearchController.java:56-61
@GetMapping(headers = "X-Api-Version=2")
public ResponseEntity<ApiResponse<PagedResponse<ProductDto.Response>>> searchV2(
        @RequestParam String q,
        Pageable pageable) {
    return ResponseEntity.ok(ApiResponse.success(productService.searchPaged(q, pageable)));
}
```

- `headers = "X-Api-Version=2"` — 같은 URL, 다른 헤더 값 → 완전히 다른 핸들러
- 응답 형태도 다름: 리스트(`List`) vs 페이징(`PagedResponse`)

---

## 10. 상품 상세 + HATEOAS 링크

```
GET /api/products/search/{id}/links
```

```bash
curl http://localhost:8080/api/products/search/1/links \
  -H "X-Api-Version: 1"
```

**Request**
| 파라미터 | 위치 | 타입 | 설명 |
|---|---|---|---|
| `id` | Path | Long | 상품 ID |

**Response (200 OK)**
```json
{
  "id": 1,
  "name": "노트북",
  "price": 1500000,
  "description": "고성능 노트북",
  "categoryName": "전자기기",
  "stockQuantity": 10,
  "active": true,
  "_links": {
    "self": {
      "href": "http://localhost:8080/api/products/search/1/links"
    },
    "product": {
      "href": "http://localhost:8080/api/v1/products/1"
    }
  }
}
```

**엣지케이스: HATEOAS (EntityModel)**

```java
// ProductSearchController.java:70-82
@GetMapping("/{id}/links")
public EntityModel<ProductDto.Response> getProductWithLinks(
        @PathVariable Long id) {
    ProductDto.Response product = productService.getProduct(id);
    return EntityModel.of(product,
            WebMvcLinkBuilder.linkTo(
                    WebMvcLinkBuilder.methodOn(ProductSearchController.class)
                            .getProductWithLinks(id)).withSelfRel(),
            WebMvcLinkBuilder.linkTo(
                    WebMvcLinkBuilder.methodOn(ProductController.class)
                            .getProduct(id)).withRel("product")
    );
}
```

- 리턴 타입: `EntityModel<ProductDto.Response>` — Spring HATEOAS 래퍼
- 응답에 `_links` 필드가 **자동으로 추가**됨
- 파서가 `EntityModel`은 리턴 타입으로 추출하지만:
  - 내부의 `ProductDto.Response`가 실제 데이터라는 것을 알 수 없음
  - `_links` 필드가 응답에 추가된다는 것을 알 수 없음
  - 다른 엔드포인트의 `ResponseEntity<ApiResponse<...>>` 래핑과 완전히 다른 응답 구조
- `ApiResponse` 래핑이 아님 → 같은 프로젝트인데 응답 형태가 불일치
