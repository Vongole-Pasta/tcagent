package com.shopone.domain.member.dto;

/**
 * 토큰 응답 DTO.
 *
 * [파서 커버] Record 추출, 혼합 타입 필드 (String, long)
 */
public record TokenResponse(
        String accessToken,
        String tokenType,
        long expiresIn
) {
    public static TokenResponse of(String accessToken, long expiresIn) {
        return new TokenResponse(accessToken, "Bearer", expiresIn);
    }
}
