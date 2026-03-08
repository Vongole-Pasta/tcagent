package com.shopone.config;

import com.shopone.global.interceptor.ApiVersionInterceptor;
import com.shopone.global.resolver.CurrentMemberArgumentResolver;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.List;

/**
 * Spring MVC 설정.
 * 커스텀 ArgumentResolver와 Interceptor를 등록한다.
 *
 * [파서 한계 #1] implements WebMvcConfigurer — 인터페이스 구현 관계 미감지
 * [API 엣지 #3] Interceptor/Resolver 등록 — 컨트롤러 분석만으로는 이 설정을 알 수 없음
 * [API 엣지 #13] CurrentMemberArgumentResolver 등록
 */
@Configuration
@RequiredArgsConstructor
public class WebMvcConfig implements WebMvcConfigurer {

    private final CurrentMemberArgumentResolver currentMemberResolver;
    private final ApiVersionInterceptor apiVersionInterceptor;

    @Override
    public void addArgumentResolvers(List<HandlerMethodArgumentResolver> resolvers) {
        resolvers.add(currentMemberResolver);
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(apiVersionInterceptor)
                .addPathPatterns("/api/**")
                .excludePathPatterns("/api/v*//**", "/api/auth/**");
    }
}
