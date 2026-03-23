package com.shopone.domain.product.repository;

import com.shopone.domain.product.entity.Product;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

/**
 * 상품 리포지토리 인터페이스.
 *
 * [파서 한계 #1] extends JpaRepository<Product, Long>
 * [파서 커버] 인터페이스, Page/Pageable 제네릭 리턴 타입
 */
public interface ProductRepository extends JpaRepository<Product, Long> {

    List<Product> findByCategoryId(Long categoryId);

    Page<Product> findByNameContaining(String keyword, Pageable pageable);

    List<Product> findByActiveTrue();
}
