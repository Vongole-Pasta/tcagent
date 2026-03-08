package com.shopone.domain.order.entity;

import com.shopone.common.BaseEntity;
import com.shopone.domain.member.entity.Address;
import com.shopone.domain.member.entity.Member;
import com.shopone.global.exception.BusinessException;
import com.shopone.global.exception.ErrorCode;
import jakarta.persistence.CascadeType;
import jakarta.persistence.Embedded;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.OneToMany;
import jakarta.persistence.Table;
import lombok.Getter;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

/**
 * 주문 엔티티.
 *
 * [파서 한계 #1] extends BaseEntity — 상속 관계 미감지
 * [파서 한계 #8] List<OrderItem> items — 제네릭 필드 타입
 * [파서 커버] 내부 static 클래스(DeliveryInfo), Lombok @Getter 혼용, 여러 관계 어노테이션
 */
@Entity
@Table(name = "orders")
@Getter
public class Order extends BaseEntity {

    @ManyToOne(fetch = jakarta.persistence.FetchType.EAGER)
    @JoinColumn(name = "member_id", nullable = false)
    private Member member;

    @Enumerated(EnumType.STRING)
    private OrderStatus status = OrderStatus.PENDING;

    @OneToMany(mappedBy = "order", cascade = CascadeType.ALL, orphanRemoval = true, fetch = jakarta.persistence.FetchType.EAGER)
    private List<OrderItem> items = new ArrayList<>();

    private BigDecimal totalAmount = BigDecimal.ZERO;

    @Embedded
    private DeliveryInfo deliveryInfo;

    protected Order() {
    }

    public Order(Member member) {
        this.member = member;
    }

    public void addItem(OrderItem item) {
        this.items.add(item);
        recalculateTotal();
    }

    public void setDeliveryInfo(DeliveryInfo deliveryInfo) {
        this.deliveryInfo = deliveryInfo;
    }

    /**
     * 주문 상태 변경 (상태 전이 검증 포함)
     */
    public void changeStatus(OrderStatus newStatus) {
        if (!this.status.canTransitionTo(newStatus)) {
            throw new BusinessException(ErrorCode.INVALID_ORDER_STATUS,
                    String.format("%s → %s 상태 변경 불가", this.status, newStatus));
        }
        this.status = newStatus;
    }

    private void recalculateTotal() {
        this.totalAmount = items.stream()
                .map(OrderItem::getSubtotal)
                .reduce(BigDecimal.ZERO, BigDecimal::add);
    }

    /**
     * 배송 정보 (내부 static 클래스).
     *
     * [파서 커버] 내부 클래스 추출 — Order$DeliveryInfo
     */
    @jakarta.persistence.Embeddable
    public static class DeliveryInfo {
        private String recipientName;
        private String phone;

        @Embedded
        private Address address;

        protected DeliveryInfo() {
        }

        public DeliveryInfo(String recipientName, String phone, Address address) {
            this.recipientName = recipientName;
            this.phone = phone;
            this.address = address;
        }

        public String getRecipientName() {
            return recipientName;
        }

        public String getPhone() {
            return phone;
        }

        public Address getAddress() {
            return address;
        }
    }
}
