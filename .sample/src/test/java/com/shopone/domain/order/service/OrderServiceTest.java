package com.shopone.domain.order.service;

import com.shopone.domain.member.entity.Address;
import com.shopone.domain.member.entity.Member;
import com.shopone.domain.member.repository.MemberRepository;
import com.shopone.domain.notification.service.NotificationService;
import com.shopone.domain.order.dto.OrderCreateRequest;
import com.shopone.domain.order.dto.OrderResponse;
import com.shopone.domain.order.entity.Order;
import com.shopone.domain.order.entity.OrderStatus;
import com.shopone.domain.order.repository.OrderRepository;
import com.shopone.domain.product.entity.Category;
import com.shopone.domain.product.entity.Product;
import com.shopone.domain.product.repository.ProductRepository;
import com.shopone.global.exception.BusinessException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;

/**
 * OrderService 단위 테스트.
 * varargs, 오버로딩 검증, 생성자 호출, 상태 전이 검증.
 */
@ExtendWith(MockitoExtension.class)
class OrderServiceTest {

    @InjectMocks
    private OrderService orderService;

    @Mock
    private OrderRepository orderRepository;

    @Mock
    private MemberRepository memberRepository;

    @Mock
    private ProductRepository productRepository;

    @Mock
    private OrderValidator orderValidator;

    @Mock
    private NotificationService notificationService;

    @Test
    @DisplayName("주문 생성 - 정상 흐름 (var 타입추론 + 생성자 호출)")
    void createOrder() {
        // given
        Member member = new Member("buyer@example.com", "김", "구매");
        Category category = new Category("식품", null);
        Product product = new Product.Builder()
                .name("사과")
                .price(BigDecimal.valueOf(3000))
                .category(category)
                .stockQuantity(100)
                .build();

        given(memberRepository.findById(1L)).willReturn(Optional.of(member));
        given(productRepository.findById(10L)).willReturn(Optional.of(product));
        given(orderRepository.save(any(Order.class))).willAnswer(inv -> inv.getArgument(0));

        OrderCreateRequest request = new OrderCreateRequest(
                1L,
                List.of(new OrderCreateRequest.OrderItemRequest(10L, 3)),
                "김구매",
                "010-1234-5678",
                new Address("강남대로 1", "서울", "06000")
        );

        // when
        OrderResponse response = orderService.createOrder(request);

        // then
        assertThat(response.items()).hasSize(1);
        verify(orderValidator).validate(any(Order.class));
        verify(notificationService).sendOrderConfirmation(any(Order.class));
    }

    @Test
    @DisplayName("주문 조회 - 미존재 시 예외")
    void getOrderNotFound() {
        // given
        given(orderRepository.findById(999L)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> orderService.getOrder(999L))
                .isInstanceOf(BusinessException.class);
    }

    @Test
    @DisplayName("주문 상태 변경 - 정상 전이 (PENDING → CONFIRMED)")
    void updateStatus() {
        // given
        Member member = new Member("test@example.com", "테", "스트");
        Order order = new Order(member);
        given(orderRepository.findById(1L)).willReturn(Optional.of(order));

        // when
        OrderResponse response = orderService.updateStatus(1L, OrderStatus.CONFIRMED);

        // then
        assertThat(response.status()).isEqualTo(OrderStatus.CONFIRMED);
    }

    @Test
    @DisplayName("주문 상태 변경 - 불가능한 전이 (DELIVERED → PENDING)")
    void updateStatusInvalid() {
        // given
        Member member = new Member("test@example.com", "테", "스트");
        Order order = new Order(member);
        order.changeStatus(OrderStatus.CONFIRMED);
        order.changeStatus(OrderStatus.SHIPPED);
        order.changeStatus(OrderStatus.DELIVERED);

        given(orderRepository.findById(1L)).willReturn(Optional.of(order));

        // when & then
        assertThatThrownBy(() -> orderService.updateStatus(1L, OrderStatus.PENDING))
                .isInstanceOf(BusinessException.class);
    }
}
