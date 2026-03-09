package com.shopone.domain.member.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;

/**
 * 로그인 요청 DTO.
 *
 * [파서 커버] Record 추출, validation 어노테이션
 */
public record LoginRequest(
        @NotBlank @Email String email,
        @NotBlank String password
) {
}
