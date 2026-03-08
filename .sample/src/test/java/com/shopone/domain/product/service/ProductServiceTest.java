package com.shopone.domain.product.service;

import com.shopone.domain.product.dto.ProductDto;
import com.shopone.domain.product.entity.Category;
import com.shopone.domain.product.entity.Product;
import com.shopone.domain.product.repository.CategoryRepository;
import com.shopone.domain.product.repository.ProductRepository;
import com.shopone.global.exception.BusinessException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;

/**
 * ProductService 단위 테스트.
 * 메서드 체이닝, static import, 빌더 패턴 호출 검증.
 */
@ExtendWith(MockitoExtension.class)
class ProductServiceTest {

    @InjectMocks
    private ProductService productService;

    @Mock
    private ProductRepository productRepository;

    @Mock
    private CategoryRepository categoryRepository;

    @Test
    @DisplayName("상품 조회 - 정상 (체이닝 findById().map().orElseThrow())")
    void getProduct() {
        // given
        Category category = new Category("전자기기", null);
        Product product = new Product.Builder()
                .name("노트북")
                .price(BigDecimal.valueOf(1500000))
                .description("고성능 노트북")
                .category(category)
                .stockQuantity(10)
                .build();

        given(productRepository.findById(1L)).willReturn(Optional.of(product));

        // when
        ProductDto.Response response = productService.getProduct(1L);

        // then
        assertThat(response.name()).isEqualTo("노트북");
        assertThat(response.categoryName()).isEqualTo("전자기기");
    }

    @Test
    @DisplayName("상품 조회 - 미존재 시 예외 (static import ErrorCode)")
    void getProductNotFound() {
        // given
        given(productRepository.findById(999L)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> productService.getProduct(999L))
                .isInstanceOf(BusinessException.class);
    }

    @Test
    @DisplayName("상품 생성 - Builder 패턴 + 카테고리 연결")
    void createProduct() {
        // given
        Category category = new Category("가전", null);
        given(categoryRepository.findById(1L)).willReturn(Optional.of(category));
        given(productRepository.save(any(Product.class))).willAnswer(inv -> inv.getArgument(0));

        ProductDto.Create request = new ProductDto.Create(
                "세탁기", BigDecimal.valueOf(800000), "드럼세탁기", 1L, 5);

        // when
        ProductDto.Response response = productService.createProduct(request);

        // then
        assertThat(response.name()).isEqualTo("세탁기");
    }

    @Test
    @DisplayName("상품 삭제 - 소프트 삭제 (deactivate)")
    void deleteProduct() {
        // given
        Product product = new Product.Builder()
                .name("테스트상품")
                .price(BigDecimal.TEN)
                .stockQuantity(1)
                .build();

        given(productRepository.findById(1L)).willReturn(Optional.of(product));

        // when
        productService.deleteProduct(1L);

        // then
        assertThat(product.isActive()).isFalse();
    }
}
