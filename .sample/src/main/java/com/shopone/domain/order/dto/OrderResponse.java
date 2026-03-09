package com.shopone.domain.order.dto;

import com.shopone.domain.order.entity.Order;
import com.shopone.domain.order.entity.OrderItem;
import com.shopone.domain.order.entity.OrderStatus;

import java.math.BigDecimal;
import java.util.List;

/**
 * 주문 응답 DTO (Record + 중첩 Record).
 *
 * [파서 커버] Record, 중첩 Record (OrderItemResponse), 정적 팩토리 메서드
 */
public record OrderResponse(
        Long id,
        String memberEmail,
        OrderStatus status,
        List<OrderItemResponse> items,
        BigDecimal totalAmount
) {

    /**
     * 주문 항목 응답 (중첩 Record)
     */
    public record OrderItemResponse(
            String productName,
            int quantity,
            BigDecimal unitPrice,
            BigDecimal subtotal
    ) {

        public static OrderItemResponse from(OrderItem item) {
            return new OrderItemResponse(
                    item.getProduct().getName(),
                    item.getQuantity(),
                    item.getUnitPrice(),
                    item.getSubtotal()
            );
        }
    }

    /**
     * Entity → DTO 변환
     */
    public static OrderResponse from(Order order) {
        List<OrderItemResponse> itemResponses = order.getItems().stream()
                .map(OrderItemResponse::from)
                .toList();
        return new OrderResponse(
                order.getId(),
                order.getMember().getEmail(),
                order.getStatus(),
                itemResponses,
                order.getTotalAmount()
        );
    }
}
