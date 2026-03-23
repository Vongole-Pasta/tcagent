package com.shopone.domain.member.controller;

import com.shopone.common.ApiResponse;
import com.shopone.common.ApiResponseCode;
import com.shopone.common.PagedResponse;
import com.shopone.domain.member.dto.MemberCreateRequest;
import com.shopone.domain.member.dto.MemberResponse;
import com.shopone.domain.member.entity.Address;
import com.shopone.domain.member.service.MemberService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import org.springframework.data.domain.Pageable;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CookieValue;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

/**
 * 회원 REST 컨트롤러 — API 엣지케이스가 가장 많이 집중된 컨트롤러.
 *
 * [API 엣지 #1] ResponseEntity<ApiResponse<MemberResponse>> — 중첩 제네릭 래핑
 * [API 엣지 #6] @RequestMapping(method = {GET, POST}) — 한 엔드포인트에 복수 HTTP 메서드
 * [API 엣지 #7] @GetMapping("/{id:[0-9]+}") — 정규식 PathVariable
 * [API 엣지 #9] produces/consumes — Content-Type 명시
 * [API 엣지 #11] MultipartFile — 파일 업로드
 * [API 엣지 #14] @ModelAttribute — 폼 데이터 바인딩
 * [API 엣지 #15] @CookieValue, @RequestHeader — 쿠키/헤더 바인딩
 * [API 엣지 #16] Pageable — 페이징 파라미터
 * [API 엣지 #19] HttpServletRequest/Response — 직접 접근
 * [파서 커버] 클래스 레벨 @RequestMapping + 메서드 레벨 매핑 결합, 다양한 HTTP 메서드
 */
@RestController
@RequestMapping(value = "/api/members", produces = MediaType.APPLICATION_JSON_VALUE)
public class MemberController {

    private final MemberService memberService;

    public MemberController(MemberService memberService) {
        this.memberService = memberService;
    }

    /**
     * 회원 생성
     * POST /api/members
     *
     * [API 엣지 #1] ResponseEntity<ApiResponse<MemberResponse>>
     */
    @PostMapping
    public ResponseEntity<ApiResponse<MemberResponse>> createMember(
            @Valid @RequestBody MemberCreateRequest request) {
        MemberResponse response = memberService.createMember(request);
        return ResponseEntity
                .status(HttpStatus.CREATED)
                .body(ApiResponse.success(ApiResponseCode.CREATED, response));
    }

    /**
     * 회원 단건 조회
     * GET /api/members/{id}
     *
     * [API 엣지 #7] 정규식 PathVariable — id는 숫자만 허용
     */
    @GetMapping("/{id:[0-9]+}")
    public ResponseEntity<ApiResponse<MemberResponse>> getMember(
            @PathVariable Long id) {
        return ResponseEntity.ok(ApiResponse.success(memberService.getMember(id)));
    }

    /**
     * 회원 목록 조회 (페이징)
     * GET /api/members
     *
     * [API 엣지 #16] Pageable — Spring이 자동 바인딩하는 페이징 파라미터
     *   → 파서가 Pageable의 내부 구조(page, size, sort)를 알 수 없음
     */
    @GetMapping
    public ResponseEntity<ApiResponse<PagedResponse<MemberResponse>>> listMembers(
            Pageable pageable) {
        return ResponseEntity.ok(ApiResponse.success(memberService.findMembers(pageable)));
    }

    /**
     * 회원 검색 (GET + POST 동시 지원)
     * GET|POST /api/members/search
     *
     * [API 엣지 #6] @RequestMapping(method = {GET, POST}) — 복수 HTTP 메서드
     *   → 파서가 method 배열 값을 어떻게 처리하는지 검증
     */
    @RequestMapping(value = "/search", method = {RequestMethod.GET, RequestMethod.POST})
    public ResponseEntity<ApiResponse<List<MemberResponse>>> searchMembers(
            @RequestParam(required = false) String keyword) {
        return ResponseEntity.ok(ApiResponse.success(memberService.searchMembers(keyword)));
    }

    /**
     * 프로필 이미지 업로드
     * POST /api/members/{id}/profile-image
     *
     * [API 엣지 #9] consumes = MULTIPART_FORM_DATA — Content-Type 제한
     * [API 엣지 #11] MultipartFile — 파일 업로드 파라미터
     */
    @PostMapping(value = "/{id}/profile-image", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<ApiResponse<String>> uploadProfileImage(
            @PathVariable Long id,
            @RequestParam("file") MultipartFile file) {
        String url = memberService.uploadProfileImage(id, file);
        return ResponseEntity.ok(ApiResponse.success(url));
    }

    /**
     * 주소 수정 (폼 데이터)
     * PUT /api/members/{id}/address
     *
     * [API 엣지 #14] @ModelAttribute — 폼 데이터 바인딩
     *   → @RequestBody와 달리 JSON이 아닌 form-urlencoded 데이터
     */
    @PutMapping("/{id}/address")
    public ResponseEntity<ApiResponse<MemberResponse>> updateAddress(
            @PathVariable Long id,
            @ModelAttribute Address address) {
        return ResponseEntity.ok(ApiResponse.success(memberService.updateAddress(id, address)));
    }

    /**
     * 현재 회원 조회 (쿠키/헤더 바인딩)
     * GET /api/members/me
     *
     * [API 엣지 #15] @CookieValue, @RequestHeader — 비표준 파라미터 바인딩
     *   → 파서가 이 어노테이션들을 파라미터 어노테이션으로 캡처하지만, 의미적 해석은 못함
     */
    @GetMapping("/me")
    public ResponseEntity<ApiResponse<MemberResponse>> getCurrentMember(
            @CookieValue(name = "SESSION_ID", required = false) String sessionId,
            @RequestHeader("X-Auth-Token") String authToken) {
        return ResponseEntity.ok(ApiResponse.success(memberService.getByToken(authToken)));
    }

    /**
     * 감사 로그 조회 (HttpServletRequest/Response 직접 사용)
     * GET /api/members/audit
     *
     * [API 엣지 #19] HttpServletRequest/Response — Servlet API 직접 접근
     *   → 파서가 파라미터 타입은 추출하지만, 이것이 요청/응답 객체라는 의미를 알 수 없음
     */
    @GetMapping("/audit")
    public void getAuditLog(
            HttpServletRequest request,
            HttpServletResponse response) {
        memberService.writeAuditLog(request, response);
    }
}
