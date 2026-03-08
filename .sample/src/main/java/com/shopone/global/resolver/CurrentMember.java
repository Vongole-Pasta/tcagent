package com.shopone.global.resolver;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * 현재 인증된 회원 ID를 주입하는 커스텀 어노테이션.
 * CurrentMemberArgumentResolver에 의해 해석된다.
 *
 * [API 엣지 #13] 커스텀 ArgumentResolver — 파서가 이 어노테이션의 의미를 알 수 없음
 *   → @PathVariable이나 @RequestParam과 달리 Spring 표준이 아닌 커스텀 어노테이션
 */
@Target(ElementType.PARAMETER)
@Retention(RetentionPolicy.RUNTIME)
public @interface CurrentMember {
}
