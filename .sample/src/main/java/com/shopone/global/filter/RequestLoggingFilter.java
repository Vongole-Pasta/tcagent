package com.shopone.global.filter;

import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.io.IOException;

/**
 * 요청/응답 로깅 필터.
 * 모든 HTTP 요청의 메서드, URI, 처리 시간을 로깅한다.
 *
 * [API 엣지 #3] Filter 계층의 조작 — 컨트롤러 함수만 보면 이 로깅이 일어나는지 알 수 없음
 *   → 요청 전후 처리를 필터에서 수행하므로, 파서가 컨트롤러만 분석해선 전체 흐름 파악 불가
 * [파서 한계 #1] implements Filter — 인터페이스 구현 관계 미감지
 */
@Component
@Order(1)
public class RequestLoggingFilter implements Filter {

    private static final Logger log = LoggerFactory.getLogger(RequestLoggingFilter.class);

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        HttpServletRequest httpReq = (HttpServletRequest) request;
        HttpServletResponse httpRes = (HttpServletResponse) response;

        long startTime = System.currentTimeMillis();
        String method = httpReq.getMethod();
        String uri = httpReq.getRequestURI();

        chain.doFilter(request, response);

        long duration = System.currentTimeMillis() - startTime;
        int status = httpRes.getStatus();

        log.info("[{}] {} {} - {}ms", method, uri, status, duration);
    }
}
