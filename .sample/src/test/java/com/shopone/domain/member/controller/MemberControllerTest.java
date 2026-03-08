package com.shopone.domain.member.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.shopone.config.WebMvcConfig;
import com.shopone.domain.member.dto.MemberCreateRequest;
import com.shopone.domain.member.dto.MemberResponse;
import com.shopone.domain.member.entity.MemberGrade;
import com.shopone.domain.member.service.MemberService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.ComponentScan;
import org.springframework.context.annotation.FilterType;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultHandlers.print;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * MemberController 단위 테스트.
 * 엔드포인트 매핑, 파라미터 바인딩, 응답 구조 검증.
 *
 * WebMvcConfig(인터셉터, ArgumentResolver)를 제외하여 컨트롤러 단위 테스트에 집중
 */
@WebMvcTest(
        controllers = MemberController.class,
        excludeFilters = @ComponentScan.Filter(
                type = FilterType.ASSIGNABLE_TYPE,
                classes = WebMvcConfig.class
        )
)
class MemberControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private MemberService memberService;

    @Test
    @DisplayName("POST /api/members - 회원 생성 성공")
    void createMember() throws Exception {
        // given
        MemberResponse response = new MemberResponse(
                1L, "test@example.com", "홍 길동", MemberGrade.BRONZE, List.of(), true);
        given(memberService.createMember(any(MemberCreateRequest.class)))
                .willReturn(response);

        MemberCreateRequest request = new MemberCreateRequest(
                "test@example.com", "홍", "길동", List.of());

        // when & then
        mockMvc.perform(post("/api/members")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andDo(print())
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.email").value("test@example.com"))
                .andExpect(jsonPath("$.code").value("CREATED"));
    }

    @Test
    @DisplayName("GET /api/members/{id} - 정규식 PathVariable 정상 동작")
    void getMember() throws Exception {
        // given
        MemberResponse response = new MemberResponse(
                1L, "test@example.com", "홍 길동", MemberGrade.BRONZE, List.of(), true);
        given(memberService.getMember(1L)).willReturn(response);

        // when & then
        mockMvc.perform(get("/api/members/1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.id").value(1));
    }

    @Test
    @DisplayName("GET /api/members/{id} - 숫자가 아닌 ID는 정규식에 매치되지 않음")
    void getMemberWithInvalidId() throws Exception {
        // 정규식 [0-9]+에 매치되지 않으므로 핸들러 매핑 실패 (405 또는 500)
        mockMvc.perform(get("/api/members/abc"))
                .andExpect(status().is5xxServerError());
    }

    @Test
    @DisplayName("GET /api/members/me - @CookieValue/@RequestHeader 바인딩")
    void getCurrentMember() throws Exception {
        // given
        MemberResponse response = new MemberResponse(
                1L, "test@example.com", "홍 길동", MemberGrade.GOLD, List.of("vip"), true);
        given(memberService.getByToken("12345")).willReturn(response);

        // when & then
        mockMvc.perform(get("/api/members/me")
                        .header("X-Auth-Token", "12345")
                        .cookie(new jakarta.servlet.http.Cookie("SESSION_ID", "session-abc")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.grade").value("GOLD"));
    }

    @Test
    @DisplayName("POST+GET /api/members/search - 복수 HTTP 메서드 지원")
    void searchMembers() throws Exception {
        // given
        given(memberService.searchMembers("홍")).willReturn(List.of());

        // GET 방식
        mockMvc.perform(get("/api/members/search").param("keyword", "홍"))
                .andExpect(status().isOk());

        // POST 방식
        mockMvc.perform(post("/api/members/search").param("keyword", "홍"))
                .andExpect(status().isOk());
    }
}
