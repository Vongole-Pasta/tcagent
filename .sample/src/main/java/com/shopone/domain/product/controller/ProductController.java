package com.shopone.domain.product.controller;

import com.shopone.common.ApiResponse;
import com.shopone.domain.product.dto.ProductDto;
import com.shopone.domain.product.service.ProductService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.MatrixVariable;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.context.request.async.DeferredResult;

import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

/**
 * 상품 REST 컨트롤러 (v1 URL 기반 API 버전).
 *
 * [API 엣지 #8] @MatrixVariable — Matrix 파라미터 바인딩 (/filter;color=red;size=L)
 * [API 엣지 #10] CompletableFuture, DeferredResult — 비동기 엔드포인트
 * [API 엣지 #17] URL 기반 API 버전 (/api/v1/products)
 * [파서 커버] 다양한 HTTP 메서드, 제네릭 리턴 타입
 */
@RestController
@RequestMapping("/api/v1/products")
public class ProductController {

    private final ProductService productService;

    public ProductController(ProductService productService) {
        this.productService = productService;
    }

    /**
     * 상품 단건 조회
     * GET /api/v1/products/{id}
     */
    @GetMapping("/{id}")
    public ResponseEntity<ApiResponse<ProductDto.Response>> getProduct(
            @PathVariable Long id) {
        return ResponseEntity.ok(ApiResponse.success(productService.getProduct(id)));
    }

    /**
     * 상품 생성
     * POST /api/v1/products
     */
    @PostMapping
    public ResponseEntity<ApiResponse<ProductDto.Response>> createProduct(
            @Valid @RequestBody ProductDto.Create request) {
        return ResponseEntity
                .status(HttpStatus.CREATED)
                .body(ApiResponse.success(productService.createProduct(request)));
    }

    /**
     * 상품 수정
     * PUT /api/v1/products/{id}
     */
    @PutMapping("/{id}")
    public ResponseEntity<ApiResponse<ProductDto.Response>> updateProduct(
            @PathVariable Long id,
            @Valid @RequestBody ProductDto.Update request) {
        return ResponseEntity.ok(ApiResponse.success(productService.updateProduct(id, request)));
    }

    /**
     * 상품 필터링 (Matrix Variable)
     * GET /api/v1/products/filter/{criteria}
     * 예: /api/v1/products/filter/attrs;color=red;size=L
     *
     * [API 엣지 #8] @MatrixVariable — 세미콜론 구분 파라미터
     *   → 파서가 @MatrixVariable 어노테이션은 캡처하지만, 파라미터 구조를 알 수 없음
     */
    @GetMapping("/filter/{criteria}")
    public ResponseEntity<ApiResponse<List<ProductDto.Response>>> filterProducts(
            @MatrixVariable Map<String, String> criteria) {
        return ResponseEntity.ok(ApiResponse.success(productService.filterProducts(criteria)));
    }

    /**
     * 비동기 상품 조회 (CompletableFuture)
     * GET /api/v1/products/async/{id}
     *
     * [API 엣지 #10] CompletableFuture — 비동기 래핑
     *   → 리턴 타입이 CompletableFuture<ResponseEntity<ApiResponse<...>>> 로 3중 중첩
     */
    @GetMapping("/async/{id}")
    public CompletableFuture<ResponseEntity<ApiResponse<ProductDto.Response>>> getProductAsync(
            @PathVariable Long id) {
        return CompletableFuture.supplyAsync(() ->
                ResponseEntity.ok(ApiResponse.success(productService.getProduct(id)))
        );
    }

    /**
     * 비동기 상품 조회 (DeferredResult)
     * GET /api/v1/products/deferred/{id}
     *
     * [API 엣지 #10] DeferredResult — Spring 비동기 래핑
     */
    @GetMapping("/deferred/{id}")
    public DeferredResult<ResponseEntity<ApiResponse<ProductDto.Response>>> getProductDeferred(
            @PathVariable Long id) {
        DeferredResult<ResponseEntity<ApiResponse<ProductDto.Response>>> result =
                new DeferredResult<>(5000L);

        CompletableFuture.supplyAsync(() -> productService.getProduct(id))
                .thenAccept(product ->
                        result.setResult(ResponseEntity.ok(ApiResponse.success(product))))
                .exceptionally(ex -> {
                    result.setErrorResult(ex);
                    return null;
                });

        return result;
    }

    /**
     * 상품 삭제
     * DELETE /api/v1/products/{id}
     */
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteProduct(@PathVariable Long id) {
        productService.deleteProduct(id);
        return ResponseEntity.noContent().build();
    }
}
