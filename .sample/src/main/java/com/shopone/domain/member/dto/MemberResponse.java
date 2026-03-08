package com.shopone.domain.member.dto;

import com.shopone.domain.member.entity.Member;
import com.shopone.domain.member.entity.MemberGrade;

import java.util.List;

/**
 * 회원 응답 DTO (Record).
 *
 * [파서 커버] Record, 다른 타입 참조(MemberGrade), 정적 팩토리 메서드
 */
public record MemberResponse(
        Long id,
        String email,
        String fullName,
        MemberGrade grade,
        List<String> tags,
        boolean active
) {

    /**
     * Entity → DTO 변환 팩토리 메서드
     */
    public static MemberResponse from(Member member) {
        return new MemberResponse(
                member.getId(),
                member.getEmail(),
                member.getFullName(),
                member.getGrade(),
                member.getTags(),
                member.isActive()
        );
    }
}
