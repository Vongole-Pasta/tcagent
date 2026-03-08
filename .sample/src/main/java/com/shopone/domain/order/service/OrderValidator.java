package com.shopone.domain.order.service;

import com.shopone.domain.order.entity.Order;
import com.shopone.domain.order.entity.OrderItem;
import com.shopone.global.exception.BusinessException;
import com.shopone.global.exception.ErrorCode;
import org.springframework.stereotype.Component;

/**
 * 주문 검증 로직.
 *
 * [파서 한계 #5] validate() 오버로딩 2개 — 파서가 구분 못함
 * [파서 한계 #3] order.getItems().stream()...forEach(item -> item.getProduct().isAvailable())
 *   → 체이닝 + 람다 조합
 * [파서 한계 #7] item -> item.getProduct().isAvailable() — 람다 파라미터 타입 미지
 * [파서 커버] 형제 메서드 호출(validateStock, validateMemberGrade — obj_name 없이 호출)
 */
@Component
public class OrderValidator {

    /**
     * 기본 주문 검증 (오버로딩 #1)
     */
    public void validate(Order order) {
        validateStock(order);
        validateMemberGrade(order);
    }

    /**
     * 엄격 모드 주문 검증 (오버로딩 #2)
     *
     * [파서 한계 #5] 동일 이름 메서드 — validate(Order) vs validate(Order, boolean)
     */
    public void validate(Order order, boolean strict) {
        validate(order);
        if (strict) {
            validatePayment(order);
        }
    }

    /**
     * 재고 검증
     *
     * [파서 한계 #3] + [파서 한계 #7] 체이닝 + 람다 조합
     */
    private void validateStock(Order order) {
        for (OrderItem item : order.getItems()) {
            if (!item.getProduct().isAvailable()) {
                throw new BusinessException(ErrorCode.INSUFFICIENT_STOCK,
                        "품절 상품: " + item.getProduct().getName());
            }
            if (item.getProduct().getStockQuantity() < item.getQuantity()) {
                throw new BusinessException(ErrorCode.INSUFFICIENT_STOCK,
                        "재고 부족: " + item.getProduct().getName());
            }
        }
    }

    /**
     * 회원 등급 기반 주문 한도 검증
     */
    private void validateMemberGrade(Order order) {
        // VIP가 아닌 회원은 1회 주문 최대 10개 상품
        if (order.getMember().getGrade() != com.shopone.domain.member.entity.MemberGrade.VIP) {
            long totalQuantity = order.getItems().stream()
                    .mapToInt(OrderItem::getQuantity)
                    .sum();
            if (totalQuantity > 10) {
                throw new BusinessException(ErrorCode.INVALID_ORDER_STATUS,
                        "일반 회원은 1회 최대 10개까지 주문 가능합니다");
            }
        }
    }

    /**
     * 결제 가능 여부 검증 (시뮬레이션)
     */
    private void validatePayment(Order order) {
        // 실제로는 PG사 연동 등
        if (order.getTotalAmount().compareTo(java.math.BigDecimal.valueOf(10_000_000)) > 0) {
            throw new BusinessException(ErrorCode.INVALID_ORDER_STATUS,
                    "1,000만원 이상 주문은 별도 승인이 필요합니다");
        }
    }
}
