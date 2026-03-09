package com.shopone.security;

import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.HttpStatusEntryPoint;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.security.web.firewall.HttpFirewall;
import org.springframework.security.web.firewall.StrictHttpFirewall;

/**
 * Spring Security 설정.
 *
 * [파서 한계 #1] @EnableWebSecurity — Spring Security 메타 어노테이션 미감지
 * [파서 한계 #1] @EnableMethodSecurity — 메서드 레벨 보안 활성화 미감지
 * [파서 한계 #3] http.csrf().disable()...authorizeHttpRequests()... — 람다 DSL 체이닝
 * [파서 한계 #9] @Configuration — Spring 스테레오타입 미감지
 * [파서 커버] @Bean 메서드, 리턴 타입 SecurityFilterChain
 */
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
@RequiredArgsConstructor
public class SecurityConfig {

    private final JwtAuthenticationFilter jwtAuthenticationFilter;

    /**
     * SecurityFilterChain 빈 — Spring Security의 핵심 설정.
     *
     * [파서 한계 #3] 람다 DSL 체이닝 — http.csrf(c -> c.disable())... 중간 타입 소실
     * [파서 한계 #7] 람다 파라미터 — auth -> auth.requestMatchers() 등 타입 미지
     */
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
                // CSRF 비활성화 (API 서버)
                .csrf(csrf -> csrf.disable())

                // H2 콘솔용 프레임 옵션 허용
                .headers(headers -> headers.frameOptions(frame -> frame.sameOrigin()))

                // 인가 규칙
                .authorizeHttpRequests(auth -> auth
                        // 인증 없이 접근 가능한 경로
                        .requestMatchers(HttpMethod.POST, "/api/auth/login").permitAll()
                        .requestMatchers(HttpMethod.POST, "/api/members").permitAll()
                        .requestMatchers(HttpMethod.GET, "/api/v1/products/**").permitAll()
                        .requestMatchers(HttpMethod.GET, "/api/products/search/**").permitAll()
                        .requestMatchers("/api/orders/stream").permitAll()
                        .requestMatchers("/api/notifications/**").permitAll()
                        .requestMatchers("/h2-console/**").permitAll()

                        // 나머지는 인증 필요
                        .anyRequest().authenticated()
                )

                // 인증 실패 시 401 반환
                .exceptionHandling(ex -> ex
                        .authenticationEntryPoint(new HttpStatusEntryPoint(
                                org.springframework.http.HttpStatus.UNAUTHORIZED))
                )

                // Session 기반 인증도 허용 (JWT와 듀얼)
                .sessionManagement(session -> session
                        .maximumSessions(1)
                )

                // JWT 필터를 UsernamePasswordAuthenticationFilter 앞에 등록
                .addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }

    /**
     * BCryptPasswordEncoder 빈.
     *
     * [파서 한계 #10] @Bean — 빈 등록 메서드를 파서가 DI 관계로 연결하지 못함
     */
    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    /**
     * HttpFirewall 빈 — @MatrixVariable (세미콜론 URL) 허용을 위한 설정.
     *
     * [파서 한계 #10] @Bean — 빈 등록 관계 미감지
     */
    @Bean
    public HttpFirewall allowSemicolonFirewall() {
        StrictHttpFirewall firewall = new StrictHttpFirewall();
        firewall.setAllowSemicolon(true);
        return firewall;
    }

    /**
     * AuthenticationManager 빈 — 로그인 시 인증 처리에 사용.
     */
    @Bean
    public AuthenticationManager authenticationManager(
            AuthenticationConfiguration authenticationConfiguration) throws Exception {
        return authenticationConfiguration.getAuthenticationManager();
    }
}
