# 알림(Notification) API — 엣지케이스 가이드

> NotificationController: 2개 엔드포인트 (`/api/notifications`)

---

## 1. SSE 구독

```bash
# SSE 스트림 — 연결이 유지되며 알림이 실시간 푸시됨
curl -N "http://localhost:8080/api/notifications/subscribe?memberId=1" \
  -H "X-Api-Version: 1"
```

**Request**
| 파라미터 | 위치 | 타입 | 설명 |
|---|---|---|---|
| `memberId` | Query | Long | 구독할 회원 ID |

**Response (200 OK, text/event-stream)**
```
event:notification
data:환영합니다, 김구매님!

event:notification
data:주문 #1이 접수되었습니다.

(연결이 유지되며, 알림 발생 시 실시간 전송. 60초 타임아웃)
```

**엣지케이스: SseEmitter (Servlet 기반 SSE)**

```java
// NotificationController.java:38-41
@GetMapping(value = "/subscribe", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
public SseEmitter subscribe(@RequestParam Long memberId) {
    return notificationService.createEmitter(memberId);
}
```

```java
// NotificationService.java:34-40 — SseEmitter 생성 로직
public SseEmitter createEmitter(Long memberId) {
    SseEmitter emitter = new SseEmitter(60_000L);
    emitters.put(memberId, emitter);
    emitter.onCompletion(() -> emitters.remove(memberId));
    emitter.onTimeout(() -> emitters.remove(memberId));
    return emitter;
}
```

- 리턴 타입: `SseEmitter`
- `produces = MediaType.TEXT_EVENT_STREAM_VALUE` — SSE 응답
- Order API의 `Flux<OrderResponse>`(Reactor/WebFlux 기반 SSE)와 달리,
  `SseEmitter`는 **전통적인 Servlet 기반 SSE** 구현
- 동일 프로젝트에서 두 가지 SSE 방식을 혼용하는 것은 실무에서 흔한 패턴
- 파서 관점 한계:
  - `SseEmitter`가 스트리밍 응답이라는 의미를 알 수 없음
  - `produces` 속성을 추출하지 못하므로 일반 JSON API와 구분 불가
  - `Flux`와 `SseEmitter` 모두 SSE이지만, 파서는 이 둘의 관계를 모름

---

## 2. 알림 일괄 발송

```bash
curl -X POST http://localhost:8080/api/notifications/send \
  -H "Content-Type: application/json" \
  -H "X-Api-Version: 1" \
  -d '{
    "memberIds": [1, 2, 3],
    "message": "금일 전 상품 10% 할인 이벤트"
  }'
```

**Request Body**
```json
{
  "memberIds": [1, 2, 3],
  "message": "금일 전 상품 10% 할인 이벤트"
}
```

**Response (200 OK)**
```
(빈 응답 본문 — 204가 아닌 200, body 없음)
```

**엣지케이스: ResponseEntity\<Void\> 반환**

```java
// NotificationController.java:47-51
@PostMapping("/send")
public ResponseEntity<Void> sendNotification(@RequestBody NotificationRequest request) {
    notificationService.sendBulk(request.memberIds(), request.message());
    return ResponseEntity.ok().build();
}
```

```java
// NotificationRequest.java — 단순 Record DTO
public record NotificationRequest(
        List<Long> memberIds,
        String message
) {}
```

- 리턴 타입: `ResponseEntity<Void>`
- 다른 엔드포인트는 `ApiResponse<T>`로 감싸서 JSON을 반환하지만,
  이 엔드포인트만 **응답 본문이 없음**
- `ResponseEntity.ok().build()` — 빌더 체이닝으로 빈 200 응답 생성
- 파서 관점 한계:
  - `Void` 제네릭 타입을 추출하지만, 이것이 "응답 본문 없음"을 의미하는지 알 수 없음
  - 같은 `ResponseEntity<T>`이지만 `T`가 `ApiResponse`, `byte[]`, `Void` 등
    여러 타입으로 사용되며, 파서는 이들의 의미 차이를 구분할 수 없음
