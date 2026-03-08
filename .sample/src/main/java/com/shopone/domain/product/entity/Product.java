package com.shopone.domain.product.entity;

import com.shopone.common.BaseEntity;
import jakarta.persistence.CollectionTable;
import jakarta.persistence.Column;
import jakarta.persistence.ElementCollection;
import jakarta.persistence.Entity;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.MapKeyColumn;
import jakarta.persistence.Table;

import java.math.BigDecimal;
import java.util.HashMap;
import java.util.Map;

/**
 * 상품 엔티티.
 *
 * [파서 한계 #1] extends BaseEntity — 상속 관계 미감지
 * [파서 한계 #4] Product$Builder 내부 클래스 — 동명 타입 충돌 가능
 * [파서 한계 #8] Map<String, String> attributes — 복합 제네릭 필드
 * [파서 한계 #17] new Product(builder) — 생성자 호출을 일반 메서드 호출로 처리
 * [파서 커버] 내부 static 클래스(Builder 패턴) 추출
 */
@Entity
@Table(name = "products")
public class Product extends BaseEntity {

    @Column(nullable = false)
    private String name;

    @Column(nullable = false)
    private BigDecimal price;

    @Column(length = 1000)
    private String description;

    @ManyToOne
    @JoinColumn(name = "category_id")
    private Category category;

    @ElementCollection
    @CollectionTable(name = "product_attributes", joinColumns = @JoinColumn(name = "product_id"))
    @MapKeyColumn(name = "attr_key")
    @Column(name = "attr_value")
    private Map<String, String> attributes = new HashMap<>();

    private int stockQuantity;

    private boolean active = true;

    protected Product() {
    }

    /**
     * Builder를 통한 생성자
     * [파서 한계 #17] new Product(builder) — 생성자를 메서드 호출로 처리
     */
    private Product(Builder builder) {
        this.name = builder.name;
        this.price = builder.price;
        this.description = builder.description;
        this.category = builder.category;
        this.stockQuantity = builder.stockQuantity;
    }

    public String getName() {
        return name;
    }

    public BigDecimal getPrice() {
        return price;
    }

    public String getDescription() {
        return description;
    }

    public Category getCategory() {
        return category;
    }

    public Map<String, String> getAttributes() {
        return attributes;
    }

    public int getStockQuantity() {
        return stockQuantity;
    }

    public boolean isActive() {
        return active;
    }

    public boolean isAvailable() {
        return active && stockQuantity > 0;
    }

    public void decreaseStock(int quantity) {
        if (this.stockQuantity < quantity) {
            throw new IllegalStateException("재고가 부족합니다: " + name);
        }
        this.stockQuantity -= quantity;
    }

    public void updateInfo(String name, BigDecimal price) {
        this.name = name;
        this.price = price;
    }

    public void deactivate() {
        this.active = false;
    }

    /**
     * Builder 패턴 내부 클래스.
     *
     * [파서 한계 #4] Product$Builder — 다른 파일에 Builder라는 이름이 있으면 충돌
     * [파서 한계 #3] builder.name(x).price(y).build() — 메서드 체이닝 끊김
     */
    public static class Builder {
        private String name;
        private BigDecimal price;
        private String description;
        private Category category;
        private int stockQuantity;

        public Builder name(String name) {
            this.name = name;
            return this;
        }

        public Builder price(BigDecimal price) {
            this.price = price;
            return this;
        }

        public Builder description(String description) {
            this.description = description;
            return this;
        }

        public Builder category(Category category) {
            this.category = category;
            return this;
        }

        public Builder stockQuantity(int stockQuantity) {
            this.stockQuantity = stockQuantity;
            return this;
        }

        public Product build() {
            return new Product(this);
        }
    }
}
