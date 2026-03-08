package com.shopone.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;

/**
 * JWT 토큰 생성/검증 유틸리티.
 *
 * [파서 한계 #3] Jwts.builder().subject()...compact() — 6단 메서드 체이닝 끊김
 * [파서 한계 #10] @Value — 프로퍼티 바인딩 미해석
 * [파서 커버] @Component 스테레오타입, 메서드 호출 해석
 */
@Component
public class JwtTokenProvider {

    private final SecretKey key;
    private final long expiration;

    /**
     * [파서 한계 #10] @Value("${jwt.secret}") — 외부 설정 주입을 파서가 감지 못함
     */
    public JwtTokenProvider(
            @Value("${jwt.secret}") String secret,
            @Value("${jwt.expiration}") long expiration) {
        this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.expiration = expiration;
    }

    /**
     * JWT 토큰 생성
     *
     * [파서 한계 #3] Jwts.builder() 체이닝 — 중간 타입(JwtBuilder)이 소실됨
     */
    public String generateToken(String email, String role) {
        var now = new Date();
        var expiryDate = new Date(now.getTime() + expiration);

        // 6단 메서드 체이닝 — 파서가 각 단계의 리턴 타입을 추적할 수 없음
        return Jwts.builder()
                .subject(email)
                .claim("role", role)
                .issuedAt(now)
                .expiration(expiryDate)
                .signWith(key)
                .compact();
    }

    /**
     * 토큰에서 이메일(subject) 추출
     */
    public String getEmailFromToken(String token) {
        return parseClaims(token).getSubject();
    }

    /**
     * 토큰 유효성 검증
     */
    public boolean validateToken(String token) {
        try {
            parseClaims(token);
            return true;
        } catch (JwtException | IllegalArgumentException e) {
            return false;
        }
    }

    /**
     * [파서 한계 #3] 체이닝 — Jwts.parser().verifyWith()...parseSignedClaims()
     */
    private Claims parseClaims(String token) {
        return Jwts.parser()
                .verifyWith(key)
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }
}
