package com.shopone.global.interceptor;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * API 버전 헤더 검증 인터셉터.
 * X-Api-Version 헤더가 없으면 400 Bad Request를 반환한다.
 *
 * [API 엣지 #3] Interceptor 계층 — 컨트롤러 도달 이전에 요청을 가로채므로 파서가 감지 불가
 * [API 엣지 #17] API 버전 관리 — 인터셉터에서 버전 헤더를 검증
 * [파서 한계 #1] implements HandlerInterceptor — 인터페이스 구현 관계 미감지
 */
@Component
public class ApiVersionInterceptor implements HandlerInterceptor {

    private static final Logger log = LoggerFactory.getLogger(ApiVersionInterceptor.class);

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler)
            throws Exception {
        // /api/v1/**, /api/v2/** 등의 버전이 명시된 경로는 패스
        String uri = request.getRequestURI();
        if (uri.matches("/api/v\\d+/.*")) {
            return true;
        }

        // 그 외 경로에서는 X-Api-Version 헤더 필요
        String version = request.getHeader("X-Api-Version");
        if (version == null || version.isBlank()) {
            log.warn("API 버전 헤더 누락: {} {}", request.getMethod(), uri);
            response.setStatus(HttpStatus.BAD_REQUEST.value());
            response.getWriter().write("{\"error\": \"X-Api-Version header is required\"}");
            return false;
        }

        return true;
    }
}
