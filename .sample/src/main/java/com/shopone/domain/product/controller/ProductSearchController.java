package com.shopone.domain.product.controller;

import com.shopone.common.ApiResponse;
import com.shopone.common.PagedResponse;
import com.shopone.domain.product.dto.ProductDto;
import com.shopone.domain.product.service.ProductService;
import org.springframework.data.domain.Pageable;
import org.springframework.hateoas.EntityModel;
import org.springframework.hateoas.server.mvc.WebMvcLinkBuilder;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 상품 검색 컨트롤러 — 헤더 기반 API 버전 관리 + HATEOAS.
 *
 * [API 엣지 #17] 헤더 기반 API 버전 — headers = "X-Api-Version=1|2"
 *   → 같은 URL이라도 헤더 값에 따라 다른 핸들러가 매핑됨
 *   → 파서가 headers 속성을 추출하지 못함
 * [API 엣지 #18] HATEOAS — EntityModel 래핑 + 링크 추가
 *   → 응답 구조가 데이터 + 하이퍼링크 조합이라 파서가 실제 응답 형태를 알 수 없음
 */
@RestController
@RequestMapping("/api/products/search")
public class ProductSearchController {

    private final ProductService productService;

    public ProductSearchController(ProductService productService) {
        this.productService = productService;
    }

    /**
     * 상품 검색 (v1 — 리스트 응답)
     * GET /api/products/search?q=... (X-Api-Version: 1)
     *
     * [API 엣지 #17] 헤더 기반 분기 — 같은 URL인데 헤더로 버전 구분
     */
    @GetMapping(headers = "X-Api-Version=1")
    public ResponseEntity<ApiResponse<List<ProductDto.Response>>> searchV1(
            @RequestParam String q) {
        return ResponseEntity.ok(ApiResponse.success(productService.search(q)));
    }

    /**
     * 상품 검색 (v2 — 페이징 응답)
     * GET /api/products/search?q=... (X-Api-Version: 2)
     *
     * [API 엣지 #17] 같은 URL, 다른 버전 → 다른 응답 형태
     */
    @GetMapping(headers = "X-Api-Version=2")
    public ResponseEntity<ApiResponse<PagedResponse<ProductDto.Response>>> searchV2(
            @RequestParam String q,
            Pageable pageable) {
        return ResponseEntity.ok(ApiResponse.success(productService.searchPaged(q, pageable)));
    }

    /**
     * 상품 상세 + HATEOAS 링크
     * GET /api/products/search/{id}/links
     *
     * [API 엣지 #18] EntityModel — HATEOAS 래핑
     *   → 응답에 _links 필드가 자동 추가되지만 파서가 이를 알 수 없음
     */
    @GetMapping("/{id}/links")
    public EntityModel<ProductDto.Response> getProductWithLinks(
            @PathVariable Long id) {
        ProductDto.Response product = productService.getProduct(id);
        return EntityModel.of(product,
                WebMvcLinkBuilder.linkTo(
                        WebMvcLinkBuilder.methodOn(ProductSearchController.class)
                                .getProductWithLinks(id)).withSelfRel(),
                WebMvcLinkBuilder.linkTo(
                        WebMvcLinkBuilder.methodOn(ProductController.class)
                                .getProduct(id)).withRel("product")
        );
    }
}
