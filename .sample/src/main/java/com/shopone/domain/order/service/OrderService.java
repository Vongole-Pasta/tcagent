package com.shopone.domain.order.service;

import com.shopone.domain.member.entity.Address;
import com.shopone.domain.member.entity.Member;
import com.shopone.domain.member.repository.MemberRepository;
import com.shopone.domain.notification.service.NotificationService;
import com.shopone.domain.order.dto.OrderCreateRequest;
import com.shopone.domain.order.dto.OrderResponse;
import com.shopone.domain.order.entity.Order;
import com.shopone.domain.order.entity.OrderItem;
import com.shopone.domain.order.entity.OrderStatus;
import com.shopone.domain.order.repository.OrderRepository;
import com.shopone.domain.product.entity.Product;
import com.shopone.domain.product.repository.ProductRepository;
import com.shopone.global.exception.BusinessException;
import com.shopone.global.exception.ErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import reactor.core.publisher.Flux;

import java.time.Duration;
import java.util.List;

/**
 * 주문 서비스.
 *
 * [파서 한계 #14] var 타입추론 — member, order, product, orderItem 등
 * [파서 한계 #17] new Order(), new OrderItem() — 생성자 호출
 * [파서 한계 #3] memberRepository.findById().orElseThrow() — 체이닝
 * [파서 커버] 필드 기반 호출(orderRepository, memberService 등), varargs(String... tags)
 */
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class OrderService {

    private final OrderRepository orderRepository;
    private final MemberRepository memberRepository;
    private final ProductRepository productRepository;
    private final OrderValidator orderValidator;
    private final NotificationService notificationService;

    /**
     * 주문 생성
     */
    @Transactional
    public OrderResponse createOrder(OrderCreateRequest request) {
        // [파서 한계 #14] var 타입추론
        var member = memberRepository.findById(request.memberId())
                .orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));

        // [파서 한계 #17] new Order(member)
        var order = new Order(member);

        // 배송 정보 설정
        if (request.deliveryAddress() != null) {
            order.setDeliveryInfo(new Order.DeliveryInfo(
                    request.recipientName(), request.phone(), request.deliveryAddress()));
        }

        // 주문 항목 추가
        for (var itemReq : request.items()) {
            var product = productRepository.findById(itemReq.productId())
                    .orElseThrow(() -> new BusinessException(ErrorCode.PRODUCT_NOT_FOUND));

            // [파서 한계 #17] new OrderItem(order, product, quantity)
            var orderItem = new OrderItem(order, product, itemReq.quantity());
            order.addItem(orderItem);
        }

        // 주문 검증
        orderValidator.validate(order);

        // 재고 차감
        order.getItems().forEach(item ->
                item.getProduct().decreaseStock(item.getQuantity()));

        orderRepository.save(order);
        notificationService.sendOrderConfirmation(order);

        return OrderResponse.from(order);
    }

    /**
     * 주문 단건 조회
     */
    public OrderResponse getOrder(Long id) {
        var order = orderRepository.findById(id)
                .orElseThrow(() -> new BusinessException(ErrorCode.ORDER_NOT_FOUND));
        return OrderResponse.from(order);
    }

    /**
     * 주문 상태 변경
     */
    @Transactional
    public OrderResponse updateStatus(Long id, OrderStatus newStatus) {
        var order = orderRepository.findById(id)
                .orElseThrow(() -> new BusinessException(ErrorCode.ORDER_NOT_FOUND));
        order.changeStatus(newStatus);
        return OrderResponse.from(order);
    }

    /**
     * 회원별 주문 목록 조회
     */
    public List<OrderResponse> getByMember(Long memberId) {
        return orderRepository.findByMemberId(memberId).stream()
                .map(OrderResponse::from)
                .toList();
    }

    /**
     * 최근 주문 스트림 (SSE/Reactive)
     *
     * [API 엣지 #10] Flux 리턴타입 — 리액티브 스트리밍
     * [API 엣지 #12] SSE — Server-Sent Events
     */
    public Flux<OrderResponse> streamRecentOrders() {
        return Flux.interval(Duration.ofSeconds(2))
                .map(tick -> {
                    List<Order> orders = orderRepository.findTop10ByOrderByCreatedAtDesc();
                    return orders.isEmpty() ? null : OrderResponse.from(orders.get(0));
                })
                .filter(response -> response != null);
    }

    /**
     * 주문 태그 추가
     *
     * [파서 커버] varargs — String... tags 파라미터
     */
    @Transactional
    public void tagOrder(Long orderId, String... tags) {
        var order = orderRepository.findById(orderId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ORDER_NOT_FOUND));
        // 태그 처리 로직 (시뮬레이션)
    }

    /**
     * 주문 인보이스 PDF 생성 (시뮬레이션)
     */
    public byte[] generateInvoice(Long orderId) {
        var order = orderRepository.findById(orderId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ORDER_NOT_FOUND));
        // 실제로는 PDF 라이브러리로 인보이스 생성
        String content = "Invoice #" + order.getId() + " - " + order.getTotalAmount();
        return content.getBytes();
    }
}
