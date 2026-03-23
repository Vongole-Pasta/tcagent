package com.shopone.domain.order.repository;

import com.shopone.domain.order.entity.Order;
import com.shopone.domain.order.entity.OrderStatus;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

/**
 * 주문 리포지토리 인터페이스.
 */
public interface OrderRepository extends JpaRepository<Order, Long> {

    List<Order> findByMemberId(Long memberId);

    List<Order> findByStatus(OrderStatus status);

    List<Order> findTop10ByOrderByCreatedAtDesc();
}
