package com.shopone.domain.member.service;

import com.shopone.common.PagedResponse;
import com.shopone.domain.member.dto.MemberCreateRequest;
import com.shopone.domain.member.dto.MemberResponse;
import com.shopone.domain.member.entity.Address;
import com.shopone.domain.member.entity.Member;
import com.shopone.domain.member.entity.MemberGrade;
import com.shopone.domain.member.repository.MemberRepository;
import com.shopone.domain.notification.service.NotificationService;
import com.shopone.global.exception.BusinessException;
import com.shopone.global.exception.ErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Pageable;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.util.List;

/**
 * 회원 서비스 — 파서 한계점이 가장 많이 집중된 클래스.
 *
 * [파서 한계 #2] this.validateEmail() — this 키워드가 EXTERNAL_CALL이 됨
 * [파서 한계 #3] memberRepository.findById(id).orElseThrow() — 메서드 체이닝 끊김
 * [파서 한계 #5] findMembers() 오버로딩 2개 — 항상 첫 번째만 선택
 * [파서 한계 #7] .filter(m -> m.isActive()) — 람다 파라미터 타입 미지
 * [파서 한계 #10] @RequiredArgsConstructor — Lombok DI 미해석
 * [파서 한계 #14] var member = ... — var 타입추론 무시
 * [파서 한계 #16] Member::getEmail, this::toResponse — 메서드 레퍼런스 미감지
 * [파서 한계 #17] new Member(...), new MemberResponse(...) — 생성자 호출 = 일반 호출
 * [파서 커버] 필드 기반 호출 해석(memberRepository.findById), 형제 메서드 호출(toResponse), 크로스 서비스 호출(notificationService.sendWelcome)
 */
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class MemberService {

    private final MemberRepository memberRepository;
    private final NotificationService notificationService;
    private final PasswordEncoder passwordEncoder;

    /**
     * 회원 생성
     */
    @Transactional
    public MemberResponse createMember(MemberCreateRequest request) {
        // [파서 한계 #2] this.validateEmail() → EXTERNAL_CALL로 분류됨
        this.validateEmail(request.email());

        // [파서 한계 #14] var — 타입 추론 무시
        // [파서 한계 #17] new Member() — 생성자 호출을 일반 메서드 호출로 처리
        var member = new Member(
                request.email(), request.firstName(), request.lastName(),
                passwordEncoder.encode(request.password()));

        if (request.addresses() != null) {
            request.addresses().forEach(member::addAddress);
        }

        // [파서 커버] 필드 기반 호출 해석 — memberRepository → MemberRepository → save 메서드
        memberRepository.save(member);

        // [파서 커버] 크로스 서비스 호출 — notificationService 필드를 통해 NotificationService.sendWelcome 해석
        notificationService.sendWelcome(member);

        return MemberResponse.from(member);
    }

    /**
     * 회원 단건 조회
     */
    public MemberResponse getMember(Long id) {
        // [파서 한계 #3] 체이닝 — findById(id).orElseThrow(...) 에서 중간 타입 소실
        var member = memberRepository.findById(id)
                .orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));
        return MemberResponse.from(member);
    }

    /**
     * 회원 목록 조회 (오버로딩 #1 — 전체)
     *
     * [파서 한계 #5] 동명 메서드 2개 → 파서가 항상 첫 번째만 선택
     * [파서 한계 #16] Member::getEmail — 메서드 레퍼런스 미감지
     */
    public List<MemberResponse> findMembers() {
        return memberRepository.findAll().stream()
                .map(MemberResponse::from)
                .toList();
    }

    /**
     * 회원 목록 조회 (오버로딩 #2 — 등급별 필터)
     *
     * [파서 한계 #5] 오버로딩된 findMembers(MemberGrade) — 파서가 구분 못함
     * [파서 한계 #7] m -> m.isActive() — 람다 파라미터 m의 타입을 알 수 없음
     * [파서 한계 #16] this::toResponse — 메서드 레퍼런스 미감지
     */
    public List<MemberResponse> findMembers(MemberGrade grade) {
        return memberRepository.findByGrade(grade).stream()
                .filter(m -> m.isActive())
                .map(this::toResponse)
                .toList();
    }

    /**
     * 페이징 회원 목록 조회
     */
    public PagedResponse<MemberResponse> findMembers(Pageable pageable) {
        return PagedResponse.from(
                memberRepository.findAll(pageable).map(MemberResponse::from)
        );
    }

    /**
     * 키워드 검색
     */
    public List<MemberResponse> searchMembers(String keyword) {
        if (keyword == null || keyword.isBlank()) {
            return findMembers();
        }
        return memberRepository
                .findByFirstNameContainingOrLastNameContaining(keyword, keyword, Pageable.unpaged())
                .map(MemberResponse::from)
                .toList();
    }

    /**
     * 주소 수정
     */
    @Transactional
    public MemberResponse updateAddress(Long id, Address newAddress) {
        var member = memberRepository.findById(id)
                .orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));
        member.updateAddress(newAddress);
        return MemberResponse.from(member);
    }

    /**
     * 프로필 이미지 업로드 (파일 처리 시뮬레이션)
     */
    @Transactional
    public String uploadProfileImage(Long id, MultipartFile file) {
        var member = memberRepository.findById(id)
                .orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));
        // 실제로는 파일 저장소에 업로드하고 URL 반환
        return "/uploads/profile/" + member.getId() + "/" + file.getOriginalFilename();
    }

    /**
     * 토큰 기반 회원 조회 (시뮬레이션)
     */
    public MemberResponse getByToken(String authToken) {
        // 실제로는 토큰 검증 후 회원 ID 추출
        Long memberId = Long.parseLong(authToken);
        return getMember(memberId);
    }

    /**
     * 감사 로그 출력 (HttpServletRequest/Response 직접 사용)
     */
    public void writeAuditLog(HttpServletRequest request, HttpServletResponse response) {
        String method = request.getMethod();
        String uri = request.getRequestURI();
        response.setHeader("X-Audit-Logged", "true");
    }

    /**
     * 이메일 중복 검증 — this.validateEmail()의 대상 메서드
     */
    private void validateEmail(String email) {
        if (memberRepository.existsByEmail(email)) {
            throw new BusinessException(ErrorCode.DUPLICATE_EMAIL);
        }
    }

    /**
     * Entity → DTO 변환 — this::toResponse의 대상 메서드
     */
    private MemberResponse toResponse(Member member) {
        return MemberResponse.from(member);
    }
}
