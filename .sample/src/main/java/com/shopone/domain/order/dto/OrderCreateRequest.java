package com.shopone.domain.order.dto;

import com.shopone.domain.member.entity.Address;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;

import java.util.List;

/**
 * 주문 생성 요청 DTO (Record + 중첩 Record).
 *
 * [파서 커버] Record, 중첩 Record (OrderItemRequest), @Valid/@Min 등 필드 어노테이션
 */
public record OrderCreateRequest(
        @NotNull Long memberId,
        @Valid List<OrderItemRequest> items,
        String recipientName,
        String phone,
        @Valid Address deliveryAddress
) {

    /**
     * 주문 항목 요청 (중첩 Record)
     */
    public record OrderItemRequest(
            @NotNull Long productId,
            @Min(1) int quantity
    ) {
    }
}
