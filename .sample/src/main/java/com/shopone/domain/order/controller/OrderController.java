package com.shopone.domain.order.controller;

import com.shopone.common.ApiResponse;
import com.shopone.domain.order.dto.OrderCreateRequest;
import com.shopone.domain.order.dto.OrderResponse;
import com.shopone.domain.order.entity.OrderStatus;
import com.shopone.domain.order.service.OrderService;
import com.shopone.global.resolver.CurrentMember;
import jakarta.validation.Valid;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.util.List;

/**
 * 주문 REST 컨트롤러.
 *
 * [API 엣지 #10] Mono, Flux — 리액티브 리턴 타입
 * [API 엣지 #12] SSE — Server-Sent Events (TEXT_EVENT_STREAM_VALUE)
 * [API 엣지 #13] @CurrentMember — 커스텀 ArgumentResolver
 * [파서 커버] 다양한 HTTP 메서드(POST, GET, PATCH), 복잡한 제네릭 리턴 타입
 */
@RestController
@RequestMapping("/api/orders")
public class OrderController {

    private final OrderService orderService;

    public OrderController(OrderService orderService) {
        this.orderService = orderService;
    }

    /**
     * 주문 생성
     * POST /api/orders
     */
    @PostMapping
    public ResponseEntity<ApiResponse<OrderResponse>> createOrder(
            @Valid @RequestBody OrderCreateRequest request) {
        return ResponseEntity
                .status(HttpStatus.CREATED)
                .body(ApiResponse.success(orderService.createOrder(request)));
    }

    /**
     * 주문 단건 조회
     * GET /api/orders/{id}
     */
    @GetMapping("/{id}")
    public ResponseEntity<ApiResponse<OrderResponse>> getOrder(
            @PathVariable Long id) {
        return ResponseEntity.ok(ApiResponse.success(orderService.getOrder(id)));
    }

    /**
     * 주문 상태 변경
     * PATCH /api/orders/{id}/status
     */
    @PatchMapping("/{id}/status")
    public ResponseEntity<ApiResponse<OrderResponse>> updateStatus(
            @PathVariable Long id,
            @RequestParam OrderStatus status) {
        return ResponseEntity.ok(ApiResponse.success(orderService.updateStatus(id, status)));
    }

    /**
     * 리액티브 주문 조회
     * GET /api/orders/reactive/{id}
     *
     * [API 엣지 #10] Mono — 리액티브 단건 래핑
     *   → 실제 응답은 동기와 동일하지만 Mono로 래핑되어 파서가 실제 타입 추출에 어려움
     */
    @GetMapping("/reactive/{id}")
    public Mono<ResponseEntity<ApiResponse<OrderResponse>>> getOrderReactive(
            @PathVariable Long id) {
        return Mono.fromCallable(() -> orderService.getOrder(id))
                .map(r -> ResponseEntity.ok(ApiResponse.success(r)));
    }

    /**
     * 최근 주문 실시간 스트림 (SSE)
     * GET /api/orders/stream
     *
     * [API 엣지 #12] Flux + TEXT_EVENT_STREAM — Server-Sent Events
     *   → 응답이 스트림이며, 파서가 produces 속성을 추출하지 못함
     */
    @GetMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<OrderResponse> streamOrders() {
        return orderService.streamRecentOrders();
    }

    /**
     * 내 주문 목록 조회
     * GET /api/orders/my
     *
     * [API 엣지 #13] @CurrentMember — 커스텀 ArgumentResolver로 주입
     *   → 파서가 @CurrentMember를 파라미터 어노테이션으로 캡처하지만,
     *     이것이 커스텀 리졸버라는 것을 알 수 없음
     */
    @GetMapping("/my")
    public ResponseEntity<ApiResponse<List<OrderResponse>>> getMyOrders(
            @CurrentMember Long memberId) {
        return ResponseEntity.ok(ApiResponse.success(orderService.getByMember(memberId)));
    }

    /**
     * 주문 인보이스 다운로드 (PDF)
     * GET /api/orders/{id}/invoice
     *
     * [API 엣지 #11] 파일 다운로드 — byte[] 리턴 + Content-Disposition 헤더
     */
    @GetMapping(value = "/{id}/invoice", produces = MediaType.APPLICATION_PDF_VALUE)
    public ResponseEntity<byte[]> downloadInvoice(@PathVariable Long id) {
        byte[] pdf = orderService.generateInvoice(id);
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=invoice-" + id + ".pdf")
                .body(pdf);
    }
}
