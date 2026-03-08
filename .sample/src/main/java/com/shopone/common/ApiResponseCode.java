package com.shopone.common;

/**
 * API 응답 코드 열거형.
 * 표준 HTTP 상태코드와 별도로 비즈니스 의미를 담는 커스텀 코드 체계.
 *
 * [API 엣지 #2] 커스텀 응답 코드 Enum — 컨트롤러 리턴타입만으로 실제 응답코드 추론 불가
 * [파서 커버] Enum 상수 추출 + 필드/생성자 정상 파싱
 */
public enum ApiResponseCode {

    SUCCESS("S2000", "성공"),
    CREATED("S2010", "생성됨"),
    BAD_REQUEST("E4000", "잘못된 요청"),
    UNAUTHORIZED("E4010", "인증 실패"),
    FORBIDDEN("E4030", "권한 없음"),
    NOT_FOUND("E4040", "리소스 없음"),
    CONFLICT("E4090", "데이터 충돌"),
    INTERNAL_ERROR("E5000", "서버 오류");

    private final String code;
    private final String message;

    ApiResponseCode(String code, String message) {
        this.code = code;
        this.message = message;
    }

    public String getCode() {
        return code;
    }

    public String getMessage() {
        return message;
    }
}
