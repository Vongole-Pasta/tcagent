package com.shopone.domain.order.entity;

/**
 * 주문 상태 열거형.
 *
 * [파서 커버] Enum 상수 + 다중 필드 + 생성자
 */
public enum OrderStatus {

    PENDING("P", "주문접수"),
    CONFIRMED("C", "주문확인"),
    SHIPPED("S", "배송중"),
    DELIVERED("D", "배송완료"),
    CANCELLED("X", "취소됨");

    private final String code;
    private final String description;

    OrderStatus(String code, String description) {
        this.code = code;
        this.description = description;
    }

    public String getCode() {
        return code;
    }

    public String getDescription() {
        return description;
    }

    /**
     * 상태 전이 가능 여부 검증
     */
    public boolean canTransitionTo(OrderStatus target) {
        return switch (this) {
            case PENDING -> target == CONFIRMED || target == CANCELLED;
            case CONFIRMED -> target == SHIPPED || target == CANCELLED;
            case SHIPPED -> target == DELIVERED;
            case DELIVERED, CANCELLED -> false;
        };
    }
}
