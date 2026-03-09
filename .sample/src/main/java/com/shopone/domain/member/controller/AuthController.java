package com.shopone.domain.member.controller;

import com.shopone.common.ApiResponse;
import com.shopone.domain.member.dto.LoginRequest;
import com.shopone.domain.member.dto.TokenResponse;
import com.shopone.domain.member.entity.Member;
import com.shopone.domain.member.repository.MemberRepository;
import com.shopone.global.exception.BusinessException;
import com.shopone.global.exception.ErrorCode;
import com.shopone.security.JwtTokenProvider;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 인증 컨트롤러 — 로그인/로그아웃 처리.
 *
 * [파서 한계 #10] @RequiredArgsConstructor — Lombok DI 미해석
 * [파서 한계 #3] authenticationManager.authenticate() 체이닝
 * [파서 커버] @RestController, @RequestMapping, @PostMapping
 */
@Slf4j
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthenticationManager authenticationManager;
    private final JwtTokenProvider jwtTokenProvider;
    private final MemberRepository memberRepository;

    @Value("${jwt.expiration}")
    private long jwtExpiration;

    /**
     * 로그인 — JWT 토큰 반환 + 세션 생성 (듀얼 인증)
     *
     * [파서 한계 #3] authenticationManager.authenticate(...) → 체이닝
     * [파서 한계 #17] new UsernamePasswordAuthenticationToken() — 생성자 호출
     */
    @PostMapping("/login")
    public ResponseEntity<ApiResponse<TokenResponse>> login(
            @Valid @RequestBody LoginRequest request,
            HttpServletRequest httpRequest) {

        try {
            // Spring Security 인증 처리
            Authentication authentication = authenticationManager.authenticate(
                    new UsernamePasswordAuthenticationToken(request.email(), request.password())
            );

            // SecurityContext에 인증 정보 설정
            SecurityContextHolder.getContext().setAuthentication(authentication);

            // 세션 생성 (Session 기반 인증용)
            HttpSession session = httpRequest.getSession(true);
            session.setAttribute("SPRING_SECURITY_CONTEXT", SecurityContextHolder.getContext());

            // 회원 등급 조회 (JWT claim에 포함)
            Member member = memberRepository.findByEmail(request.email())
                    .orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));
            member.recordLogin();

            // JWT 토큰 생성
            String token = jwtTokenProvider.generateToken(
                    request.email(), member.getGrade().name());

            log.info("로그인 성공: {} (세션: {})", request.email(), session.getId());

            return ResponseEntity.ok(
                    ApiResponse.success(TokenResponse.of(token, jwtExpiration)));

        } catch (BadCredentialsException e) {
            // 로그인 실패 시 실패 횟수 증가
            memberRepository.findByEmail(request.email())
                    .ifPresent(Member::recordLoginFailure);
            throw new BusinessException(ErrorCode.INVALID_CREDENTIALS);
        }
    }

    /**
     * 로그아웃 — 세션 무효화
     */
    @PostMapping("/logout")
    public ResponseEntity<Void> logout(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        if (session != null) {
            session.invalidate();
        }
        SecurityContextHolder.clearContext();
        return ResponseEntity.ok().build();
    }
}
