package com.shopone.domain.member.service;

import com.shopone.domain.member.dto.MemberCreateRequest;
import com.shopone.domain.member.dto.MemberResponse;
import com.shopone.domain.member.entity.Member;
import com.shopone.domain.member.entity.MemberGrade;
import com.shopone.domain.member.repository.MemberRepository;
import com.shopone.domain.notification.service.NotificationService;
import com.shopone.global.exception.BusinessException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;

/**
 * MemberService 단위 테스트.
 * 호출 해석(필드 기반, 형제 메서드, 크로스 서비스)과 비즈니스 로직 검증.
 */
@ExtendWith(MockitoExtension.class)
class MemberServiceTest {

    @InjectMocks
    private MemberService memberService;

    @Mock
    private MemberRepository memberRepository;

    @Mock
    private NotificationService notificationService;

    @Test
    @DisplayName("회원 생성 - 정상 흐름 (필드 기반 호출 + 크로스 서비스 호출)")
    void createMember() {
        // given
        given(memberRepository.existsByEmail(anyString())).willReturn(false);
        given(memberRepository.save(any(Member.class))).willAnswer(invocation -> {
            Member member = invocation.getArgument(0);
            // 리플렉션으로 ID 설정 (시뮬레이션)
            return member;
        });

        MemberCreateRequest request = new MemberCreateRequest(
                "new@example.com", "김", "철수", List.of());

        // when
        MemberResponse response = memberService.createMember(request);

        // then
        assertThat(response.email()).isEqualTo("new@example.com");
        verify(notificationService).sendWelcome(any(Member.class));
    }

    @Test
    @DisplayName("회원 생성 - 이메일 중복 시 예외 (this.validateEmail 호출)")
    void createMemberDuplicateEmail() {
        // given
        given(memberRepository.existsByEmail("exist@example.com")).willReturn(true);

        MemberCreateRequest request = new MemberCreateRequest(
                "exist@example.com", "김", "영희", List.of());

        // when & then
        assertThatThrownBy(() -> memberService.createMember(request))
                .isInstanceOf(BusinessException.class);
    }

    @Test
    @DisplayName("회원 조회 - 존재하지 않는 ID (체이닝 orElseThrow)")
    void getMemberNotFound() {
        // given
        given(memberRepository.findById(999L)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> memberService.getMember(999L))
                .isInstanceOf(BusinessException.class);
    }

    @Test
    @DisplayName("회원 목록 조회 - 오버로딩 #1 (전체)")
    void findMembersAll() {
        // given
        Member member = new Member("test@example.com", "홍", "길동");
        given(memberRepository.findAll()).willReturn(List.of(member));

        // when
        List<MemberResponse> result = memberService.findMembers();

        // then
        assertThat(result).hasSize(1);
    }

    @Test
    @DisplayName("회원 목록 조회 - 오버로딩 #2 (등급별 + 람다 필터)")
    void findMembersByGrade() {
        // given
        Member activeMember = new Member("active@example.com", "활", "동");
        given(memberRepository.findByGrade(MemberGrade.GOLD)).willReturn(List.of(activeMember));

        // when
        List<MemberResponse> result = memberService.findMembers(MemberGrade.GOLD);

        // then
        assertThat(result).hasSize(1);
    }
}
