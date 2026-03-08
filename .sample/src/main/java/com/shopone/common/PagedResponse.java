package com.shopone.common;

import java.util.List;

/**
 * 페이징 응답 래퍼 (Record).
 *
 * [API 엣지 #16] Pageable 파라미터의 응답 형태
 * [파서 커버] Record 추출, record 컴포넌트를 필드로 변환, 제네릭 타입 파라미터
 */
public record PagedResponse<T>(
        List<T> content,
        int page,
        int size,
        long totalElements,
        int totalPages
) {

    /**
     * Spring Page 객체로부터 PagedResponse 생성하는 유틸리티 메서드
     */
    public static <T> PagedResponse<T> from(org.springframework.data.domain.Page<T> springPage) {
        return new PagedResponse<>(
                springPage.getContent(),
                springPage.getNumber(),
                springPage.getSize(),
                springPage.getTotalElements(),
                springPage.getTotalPages()
        );
    }
}
