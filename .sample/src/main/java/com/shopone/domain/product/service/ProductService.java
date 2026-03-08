package com.shopone.domain.product.service;

import com.shopone.common.PagedResponse;
import com.shopone.domain.product.dto.ProductDto;
import com.shopone.domain.product.entity.Category;
import com.shopone.domain.product.entity.Product;
import com.shopone.domain.product.repository.CategoryRepository;
import com.shopone.domain.product.repository.ProductRepository;
import com.shopone.global.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

// [파서 한계 #6] static import — 파서가 static import를 해석하지 못함
//   → PRODUCT_NOT_FOUND, CATEGORY_NOT_FOUND 직접 참조 시 해당 타입과의 관계 누락
import static com.shopone.global.exception.ErrorCode.PRODUCT_NOT_FOUND;
import static com.shopone.global.exception.ErrorCode.CATEGORY_NOT_FOUND;

/**
 * 상품 서비스.
 *
 * [파서 한계 #3] productRepository.findById(id).map().orElseThrow() — 메서드 체이닝 끊김
 * [파서 한계 #6] import static ErrorCode.PRODUCT_NOT_FOUND — static import 미처리
 * [파서 한계 #14] var category = ... — var 타입추론 무시
 * [파서 한계 #17] new Product.Builder()...build() — 생성자 + 빌더 체이닝
 * [파서 한계 #16] ProductDto.Response::from — 메서드 레퍼런스 미감지
 */
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ProductService {

    private final ProductRepository productRepository;
    private final CategoryRepository categoryRepository;

    /**
     * 상품 단건 조회
     */
    public ProductDto.Response getProduct(Long id) {
        // [파서 한계 #3] 체이닝 — findById().map().orElseThrow()
        // [파서 한계 #16] ProductDto.Response::from — 메서드 레퍼런스
        return productRepository.findById(id)
                .map(ProductDto.Response::from)
                .orElseThrow(() -> new BusinessException(PRODUCT_NOT_FOUND));
    }

    /**
     * 상품 생성
     */
    @Transactional
    public ProductDto.Response createProduct(ProductDto.Create request) {
        // [파서 한계 #14] var — 타입 추론 무시
        // [파서 한계 #6] CATEGORY_NOT_FOUND — static import 미처리
        var category = categoryRepository.findById(request.getCategoryId())
                .orElseThrow(() -> new BusinessException(CATEGORY_NOT_FOUND));

        // [파서 한계 #17] new Product.Builder() — 생성자 호출
        // [파서 한계 #3] 빌더 체이닝 — name().price().build()
        var product = new Product.Builder()
                .name(request.getName())
                .price(request.getPrice())
                .description(request.getDescription())
                .category(category)
                .stockQuantity(request.getStockQuantity())
                .build();

        productRepository.save(product);
        return ProductDto.Response.from(product);
    }

    /**
     * 상품 수정
     */
    @Transactional
    public ProductDto.Response updateProduct(Long id, ProductDto.Update request) {
        var product = productRepository.findById(id)
                .orElseThrow(() -> new BusinessException(PRODUCT_NOT_FOUND));
        product.updateInfo(request.getName(), request.getPrice());
        return ProductDto.Response.from(product);
    }

    /**
     * 상품 삭제 (소프트 삭제)
     */
    @Transactional
    public void deleteProduct(Long id) {
        var product = productRepository.findById(id)
                .orElseThrow(() -> new BusinessException(PRODUCT_NOT_FOUND));
        product.deactivate();
    }

    /**
     * 상품 검색 (키워드)
     */
    public List<ProductDto.Response> search(String keyword) {
        return productRepository.findByNameContaining(keyword, Pageable.unpaged())
                .map(ProductDto.Response::from)
                .toList();
    }

    /**
     * 상품 검색 (페이징)
     */
    public PagedResponse<ProductDto.Response> searchPaged(String keyword, Pageable pageable) {
        return PagedResponse.from(
                productRepository.findByNameContaining(keyword, pageable)
                        .map(ProductDto.Response::from)
        );
    }

    /**
     * 상품 필터링 (속성 기반)
     */
    public List<ProductDto.Response> filterProducts(Map<String, String> criteria) {
        // 간단한 필터 구현: 전체 조회 후 메모리 필터
        return productRepository.findByActiveTrue().stream()
                .filter(product -> matchesCriteria(product, criteria))
                .map(ProductDto.Response::from)
                .collect(Collectors.toList());
    }

    private boolean matchesCriteria(Product product, Map<String, String> criteria) {
        for (Map.Entry<String, String> entry : criteria.entrySet()) {
            String attrValue = product.getAttributes().get(entry.getKey());
            if (attrValue == null || !attrValue.equalsIgnoreCase(entry.getValue())) {
                return false;
            }
        }
        return true;
    }
}
