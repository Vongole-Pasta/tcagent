package com.shopone.domain.member.dto;

import com.shopone.domain.member.entity.Address;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;

import java.util.List;

/**
 * 회원 생성 요청 DTO (Record).
 *
 * [파서 커버] Record 추출, record 컴포넌트를 필드로 변환, 필드 어노테이션(@NotBlank, @Email, @Valid)
 */
public record MemberCreateRequest(
        @NotBlank @Email String email,
        @NotBlank String firstName,
        @NotBlank String lastName,
        String password,
        @Valid List<Address> addresses
) {
}
