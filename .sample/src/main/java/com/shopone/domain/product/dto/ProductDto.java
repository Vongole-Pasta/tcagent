package com.shopone.domain.product.dto;

import com.shopone.domain.product.entity.Product;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.math.BigDecimal;

/**
 * 상품 관련 DTO 모음 (내부 static 클래스/Record 혼용).
 *
 * [파서 한계 #4] ProductDto$Create, ProductDto$Update, ProductDto$Response — 동명 타입 충돌 가능
 *   → 다른 파일에 Create, Update, Response 라는 이름의 클래스가 있으면 마지막 등록이 우선
 * [파서 커버] 한 파일 내 여러 내부 클래스/Record 추출
 */
public class ProductDto {

    /**
     * 상품 생성 요청 (일반 static 클래스 — Lombok 미사용)
     */
    public static class Create {
        @NotBlank
        private String name;

        @NotNull
        private BigDecimal price;

        private String description;
        private Long categoryId;
        private int stockQuantity;

        public Create() {
        }

        public Create(String name, BigDecimal price, String description, Long categoryId, int stockQuantity) {
            this.name = name;
            this.price = price;
            this.description = description;
            this.categoryId = categoryId;
            this.stockQuantity = stockQuantity;
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

        public Long getCategoryId() {
            return categoryId;
        }

        public int getStockQuantity() {
            return stockQuantity;
        }
    }

    /**
     * 상품 수정 요청
     */
    public static class Update {
        private String name;
        private BigDecimal price;

        public Update() {
        }

        public Update(String name, BigDecimal price) {
            this.name = name;
            this.price = price;
        }

        public String getName() {
            return name;
        }

        public BigDecimal getPrice() {
            return price;
        }
    }

    /**
     * 상품 응답 (Record)
     *
     * [파서 한계 #4] Response라는 이름이 다른 파일에도 있으면 동명 충돌
     */
    public record Response(
            Long id,
            String name,
            BigDecimal price,
            String description,
            String categoryName,
            int stockQuantity,
            boolean active
    ) {

        /**
         * Entity → DTO 변환
         */
        public static Response from(Product product) {
            return new Response(
                    product.getId(),
                    product.getName(),
                    product.getPrice(),
                    product.getDescription(),
                    product.getCategory() != null ? product.getCategory().getName() : null,
                    product.getStockQuantity(),
                    product.isActive()
            );
        }
    }
}
