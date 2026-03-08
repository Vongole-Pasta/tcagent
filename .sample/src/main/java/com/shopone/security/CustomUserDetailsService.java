package com.shopone.security;

import com.shopone.domain.member.entity.Member;
import com.shopone.domain.member.repository.MemberRepository;
import com.shopone.global.exception.BusinessException;
import com.shopone.global.exception.ErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * Spring Security UserDetailsService 구현체.
 *
 * [파서 한계 #1] implements UserDetailsService — 인터페이스 구현 관계 미감지
 * [파서 한계 #10] @RequiredArgsConstructor — Lombok DI 미해석
 * [파서 한계 #17] new User(...) — 생성자 호출을 일반 메서드 호출로 처리
 * [파서 커버] @Service 스테레오타입, 필드 기반 호출 해석
 */
@Service
@RequiredArgsConstructor
public class CustomUserDetailsService implements UserDetailsService {

    private final MemberRepository memberRepository;

    /**
     * 이메일로 회원 조회 → Spring Security UserDetails 변환
     *
     * [파서 한계 #3] memberRepository.findByEmail().orElseThrow() — 메서드 체이닝 끊김
     * [파서 한계 #17] new User(email, password, authorities) — 생성자 호출
     * [파서 한계 #17] new SimpleGrantedAuthority("ROLE_" + grade) — 동적 문자열 생성
     */
    @Override
    public UserDetails loadUserByUsername(String email) throws UsernameNotFoundException {
        Member member = memberRepository.findByEmail(email)
                .orElseThrow(() -> new UsernameNotFoundException("회원을 찾을 수 없습니다: " + email));

        if (!member.isActive()) {
            throw new BusinessException(ErrorCode.ACCESS_DENIED, "비활성화된 계정입니다");
        }

        // 회원 등급을 Spring Security 권한(Role)으로 변환
        var authority = new SimpleGrantedAuthority("ROLE_" + member.getGrade().name());

        return new User(
                member.getEmail(),
                member.getPassword(),
                List.of(authority)
        );
    }
}
