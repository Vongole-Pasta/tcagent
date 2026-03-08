# 주문(Order) API — 엣지케이스 가이드

> OrderController: 7개 엔드포인트 (`/api/orders`)

---

## 1. 주문 생성

```
POST /api/orders
Content-Type: application/json
```

```bash
curl -X POST http://localhost:8080/api/orders \
  -H "Content-Type: application/json" \
  -H "X-Api-Version: 1" \
  -d '{
    "memberId": 1,
    "items": [
      { "productId": 1, "quantity": 2 },
      { "productId": 2, "quantity": 1 }
    ],
    "recipientName": "홍길동",
    "phone": "010-1234-5678",
    "deliveryAddress": {
      "street": "강남대로 1",
      "city": "서울",
      "zipCode": "06000"
    }
  }'
```

**Request Body**
```json
{
  "memberId": 1,
  "items": [
    { "productId": 1, "quantity": 2 },
    { "productId": 2, "quantity": 1 }
  ],
  "recipientName": "홍길동",
  "phone": "010-1234-5678",
  "deliveryAddress": {
    "street": "강남대로 1",
    "city": "서울",
    "zipCode": "06000"
  }
}
```

**Response (201 Created)**
```json
{
  "code": "SUCCESS",
  "data": {
    "id": 1,
    "memberEmail": "hong@example.com",
    "status": "PENDING",
    "items": [
      {
        "productName": "노트북",
        "quantity": 2,
        "unitPrice": 1500000,
        "subtotal": 3000000
      },
      {
        "productName": "마우스",
        "quantity": 1,
        "unitPrice": 35000,
        "subtotal": 35000
      }
    ],
    "totalAmount": 3035000
  },
  "meta": { ... }
}
```

**엣지케이스: 중첩 Record Request Body**

```java
// OrderController.java:49-55
@PostMapping
public ResponseEntity<ApiResponse<OrderResponse>> createOrder(
        @Valid @RequestBody OrderCreateRequest request) {
    return ResponseEntity
            .status(HttpStatus.CREATED)
            .body(ApiResponse.success(orderService.createOrder(request)));
}
```

```java
// OrderCreateRequest.java — Record 안에 중첩 Record
public record OrderCreateRequest(
        Long memberId,
        List<OrderItemRequest> items,
        String recipientName,
        String phone,
        Address deliveryAddress
) {
    public record OrderItemRequest(Long productId, int quantity) {}
}
```

- 내부에 `OrderItemRequest` 중첩 Record 포함
- `deliveryAddress` 필드는 `Address` 임베더블 엔티티를 DTO로 직접 사용
- 파서가 `OrderCreateRequest`의 record 컴포넌트는 추출하지만,
  중첩 Record `OrderItemRequest`는 별도 타입으로 추출됨 → qualname이 `OrderCreateRequest$OrderItemRequest`
- 다른 파일에도 비슷한 이름(`OrderItemResponse` 등)이 있으면 동명 충돌 가능

---

## 2. 주문 단건 조회

```
GET /api/orders/{id}
```

```bash
curl http://localhost:8080/api/orders/1 \
  -H "X-Api-Version: 1"
```

**Request**
| 파라미터 | 위치 | 타입 | 설명 |
|---|---|---|---|
| `id` | Path | Long | 주문 ID |

**Response (200 OK)**: 주문 생성 응답과 동일한 구조

---

## 3. 주문 상태 변경

```
PATCH /api/orders/{id}/status?status=CONFIRMED
```

```bash
curl -X PATCH "http://localhost:8080/api/orders/1/status?status=CONFIRMED" \
  -H "X-Api-Version: 1"
```

**Request**
| 파라미터 | 위치 | 타입 | 설명 |
|---|---|---|---|
| `id` | Path | Long | 주문 ID |
| `status` | Query | OrderStatus | 변경할 상태 (`PENDING`, `CONFIRMED`, `SHIPPED`, `DELIVERED`, `CANCELLED`) |

**Response (200 OK)**
```json
{
  "code": "SUCCESS",
  "data": {
    "id": 1,
    "status": "CONFIRMED",
    ...
  },
  "meta": { ... }
}
```

**상태 전이 규칙** (컨트롤러 코드만으로는 알 수 없음):
```
PENDING → CONFIRMED, CANCELLED
CONFIRMED → SHIPPED, CANCELLED
SHIPPED → DELIVERED
DELIVERED → (변경 불가)
CANCELLED → (변경 불가)
```

**엣지케이스: Enum을 @RequestParam으로 바인딩**

```java
// OrderController.java:71-76
@PatchMapping("/{id}/status")
public ResponseEntity<ApiResponse<OrderResponse>> updateStatus(
        @PathVariable Long id,
        @RequestParam OrderStatus status) {
    return ResponseEntity.ok(ApiResponse.success(orderService.updateStatus(id, status)));
}
```

```java
// OrderStatus.java — Enum에 상태 전이 로직 내장
public enum OrderStatus {
    PENDING, CONFIRMED, SHIPPED, DELIVERED, CANCELLED;

    public boolean canTransitionTo(OrderStatus target) {
        return switch (this) {
            case PENDING -> target == CONFIRMED || target == CANCELLED;
            case CONFIRMED -> target == SHIPPED || target == CANCELLED;
            case SHIPPED -> target == DELIVERED;
            default -> false;
        };
    }
}
```

- Spring이 문자열 `"CONFIRMED"`를 `OrderStatus.CONFIRMED`으로 자동 변환
- 파서는 `OrderStatus` 타입을 추출하지만, 허용되는 값 목록을 Enum 정의에서 가져와야 함
- 상태 전이 규칙은 `OrderStatus.canTransitionTo()` + `Order.changeStatus()`에 있으므로
  컨트롤러 시그니처만으로는 절대 파악 불가

---

## 4. 리액티브 주문 조회 (Mono)

```
GET /api/orders/reactive/{id}
```

```bash
curl http://localhost:8080/api/orders/reactive/1 \
  -H "X-Api-Version: 1"
```

**Request**
| 파라미터 | 위치 | 타입 | 설명 |
|---|---|---|---|
| `id` | Path | Long | 주문 ID |

**Response (200 OK)**: 주문 조회와 동일한 JSON

**엣지케이스: Mono 리액티브 래핑**

```java
// OrderController.java:85-90
@GetMapping("/reactive/{id}")
public Mono<ResponseEntity<ApiResponse<OrderResponse>>> getOrderReactive(
        @PathVariable Long id) {
    return Mono.fromCallable(() -> orderService.getOrder(id))
            .map(r -> ResponseEntity.ok(ApiResponse.success(r)));
}
```

- 리턴 타입: `Mono<ResponseEntity<ApiResponse<OrderResponse>>>`
- 실제 응답은 동기 버전(`GET /api/orders/{id}`)과 완전히 동일
- 하지만 파서가 추출하는 리턴 타입 layout:
  `["Mono", "ResponseEntity", "ApiResponse", "OrderResponse"]`
- `Mono`는 Reactor 라이브러리의 비동기 래퍼인데, 파서는 이것이 인프라 래퍼인지 실제 응답 타입인지 구분할 수 없음
- 동일 프로젝트에서 동기(`ResponseEntity<...>`)와 리액티브(`Mono<ResponseEntity<...>>`)를 혼용하는 것은 실무에서 흔한 패턴

---

## 5. 최근 주문 실시간 스트림 (SSE)

```
GET /api/orders/stream
Accept: text/event-stream
```

```bash
# SSE 스트림 — 연결이 유지되며 데이터가 계속 푸시됨
curl -N http://localhost:8080/api/orders/stream \
  -H "X-Api-Version: 1"
```

**Request**: 없음 (파라미터 없이 호출, SSE 연결)

**Response (200 OK, text/event-stream)**
```
data:{"id":1,"memberEmail":"hong@example.com","status":"PENDING",...}

data:{"id":2,"memberEmail":"kim@example.com","status":"CONFIRMED",...}

data:{"id":1,"memberEmail":"hong@example.com","status":"PENDING",...}

(2초 간격으로 계속 전송)
```

**엣지케이스: Flux + Server-Sent Events**

```java
// OrderController.java:99-102
@GetMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
public Flux<OrderResponse> streamOrders() {
    return orderService.streamRecentOrders();
}
```

- `produces = MediaType.TEXT_EVENT_STREAM_VALUE` — SSE 응답
- 일반 REST API와 완전히 다른 동작:
  - 연결이 유지됨 (long-lived connection)
  - 응답이 한 번이 아니라 **여러 번** 전송됨
  - Content-Type이 `text/event-stream`
- 파서가 `Flux`를 리턴 타입으로 추출하지만:
  - 이것이 스트리밍 응답이라는 의미를 알 수 없음
  - `produces` 속성을 추출하지 못하므로 JSON API와 구분 불가
  - 개별 이벤트의 데이터 형태(`OrderResponse`)는 추출 가능하지만,
    "이 API는 여러 건을 스트리밍한다"는 정보가 없음

---

## 6. 내 주문 목록 조회 (커스텀 ArgumentResolver)

```
GET /api/orders/my
X-Member-Id: 1
```

```bash
curl http://localhost:8080/api/orders/my \
  -H "X-Api-Version: 1" \
  -H "X-Member-Id: 1"
```

**Request**
| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| `X-Member-Id` | Header | Long | Y | 회원 ID (커스텀 ArgumentResolver가 추출) |

**Response (200 OK)**
```json
{
  "code": "SUCCESS",
  "data": [
    { "id": 1, "memberEmail": "hong@example.com", "status": "PENDING", ... }
  ],
  "meta": { ... }
}
```

**엣지케이스: 커스텀 @CurrentMember ArgumentResolver**

```java
// OrderController.java:112-116
@GetMapping("/my")
public ResponseEntity<ApiResponse<List<OrderResponse>>> getMyOrders(
        @CurrentMember Long memberId) {
    return ResponseEntity.ok(ApiResponse.success(orderService.getByMember(memberId)));
}
```

```java
// CurrentMemberArgumentResolver.java — 실제 값 주입 로직
@Override
public Object resolveArgument(...) {
    String memberId = request.getHeader("X-Member-Id");
    if (memberId == null) {
        throw new BusinessException(ErrorCode.UNAUTHORIZED);
    }
    return Long.parseLong(memberId);
}
```

- `@CurrentMember`는 Spring 표준이 아닌 **프로젝트 커스텀 어노테이션**
- 실제 값은 `CurrentMemberArgumentResolver`가 `X-Member-Id` 헤더에서 추출
- 파서가 `@CurrentMember`를 파라미터 어노테이션으로 캡처하지만:
  - `@PathVariable`, `@RequestParam`과 달리 Spring 표준이 아님
  - 값의 출처(헤더? 세션? 토큰?)를 파서가 알 수 없음
  - `CurrentMemberArgumentResolver`와 이 파라미터의 연결 관계를 파서가 추적할 수 없음
  - `WebMvcConfig`에서 리졸버를 등록하는 것도 파서가 감지하지 못함

**관련 파일 체인** (파서가 추적할 수 없는 연결):
```
OrderController.getMyOrders(@CurrentMember Long memberId)
    ↑ 값 주입
CurrentMemberArgumentResolver.resolveArgument()
    ↑ 등록
WebMvcConfig.addArgumentResolvers()
```

---

## 7. 주문 인보이스 다운로드 (PDF)

```
GET /api/orders/{id}/invoice
Accept: application/pdf
```

```bash
curl http://localhost:8080/api/orders/1/invoice \
  -H "X-Api-Version: 1" \
  -o invoice-1.pdf
```

**Request**
| 파라미터 | 위치 | 타입 | 설명 |
|---|---|---|---|
| `id` | Path | Long | 주문 ID |

**Response (200 OK)**
```
Content-Type: application/pdf
Content-Disposition: attachment; filename=invoice-1.pdf

(바이너리 PDF 데이터)
```

**엣지케이스: 파일 다운로드**

```java
// OrderController.java:124-130
@GetMapping(value = "/{id}/invoice", produces = MediaType.APPLICATION_PDF_VALUE)
public ResponseEntity<byte[]> downloadInvoice(@PathVariable Long id) {
    byte[] pdf = orderService.generateInvoice(id);
    return ResponseEntity.ok()
            .header(HttpHeaders.CONTENT_DISPOSITION,
                    "attachment; filename=invoice-" + id + ".pdf")
            .body(pdf);
}
```

- 리턴 타입: `ResponseEntity<byte[]>`
- `produces = MediaType.APPLICATION_PDF_VALUE`
- 응답 헤더에 `Content-Disposition: attachment`가 설정됨
- 다른 엔드포인트는 모두 JSON을 반환하지만, 이 엔드포인트만 **바이너리 파일**을 반환
- 파서가 `byte[]`를 리턴 타입으로 추출하지만:
  - 이것이 PDF 파일이라는 것은 `produces` 속성에서만 알 수 있는데, 파서가 추출 못함
  - `Content-Disposition` 헤더 설정은 메서드 본문에 있어서 시그니처만으로 파악 불가
  - 같은 `GET /api/orders/{id}/...` 패턴이지만 `/invoice`만 바이너리 응답
