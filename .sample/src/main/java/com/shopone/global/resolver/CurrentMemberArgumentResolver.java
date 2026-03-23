package com.shopone.global.resolver;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.core.MethodParameter;
import org.springframework.stereotype.Component;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;

/**
 * @CurrentMember 어노테이션을 처리하는 커스텀 ArgumentResolver.
 * X-Member-Id 헤더에서 회원 ID를 추출하여 컨트롤러 파라미터에 주입한다.
 *
 * [API 엣지 #13] HandlerMethodArgumentResolver — 컨트롤러 파라미터가 어디서 오는지 파서가 알 수 없음
 * [파서 한계 #1] implements HandlerMethodArgumentResolver — 인터페이스 구현 관계 미감지
 */
@Component
public class CurrentMemberArgumentResolver implements HandlerMethodArgumentResolver {

    @Override
    public boolean supportsParameter(MethodParameter parameter) {
        return parameter.hasParameterAnnotation(CurrentMember.class);
    }

    @Override
    public Object resolveArgument(MethodParameter parameter,
                                  ModelAndViewContainer mavContainer,
                                  NativeWebRequest webRequest,
                                  WebDataBinderFactory binderFactory) {
        HttpServletRequest request = (HttpServletRequest) webRequest.getNativeRequest();
        String memberIdHeader = request.getHeader("X-Member-Id");
        if (memberIdHeader == null || memberIdHeader.isBlank()) {
            throw new IllegalArgumentException("X-Member-Id 헤더가 필요합니다");
        }
        return Long.valueOf(memberIdHeader);
    }
}
