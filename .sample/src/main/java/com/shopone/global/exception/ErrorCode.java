package com.shopone.global.exception;

import org.springframework.http.HttpStatus;

/**
 * 비즈니스 에러 코드 열거형.
 * HTTP 상태코드 + 커스텀 에러코드 + 한글 메시지를 함께 관리.
 *
 * [API 엣지 #2] 커스텀 응답코드 — 컨트롤러 리턴타입만으로는 실제 에러코드 추론 불가
 * [API 엣지 #5] @ResponseStatus 대신 ErrorCode로 상태코드 관리 — 파서가 감지 못함
 * [파서 커버] Enum 상수 + 다중 인자 생성자 정상 파싱
 */
public enum ErrorCode {

    // 회원 관련
    MEMBER_NOT_FOUND(HttpStatus.NOT_FOUND, "E4041", "회원을 찾을 수 없습니다"),
    DUPLICATE_EMAIL(HttpStatus.CONFLICT, "E4091", "이미 사용중인 이메일입니다"),

    // 상품 관련
    PRODUCT_NOT_FOUND(HttpStatus.NOT_FOUND, "E4042", "상품을 찾을 수 없습니다"),
    CATEGORY_NOT_FOUND(HttpStatus.NOT_FOUND, "E4043", "카테고리를 찾을 수 없습니다"),

    // 주문 관련
    ORDER_NOT_FOUND(HttpStatus.NOT_FOUND, "E4044", "주문을 찾을 수 없습니다"),
    INSUFFICIENT_STOCK(HttpStatus.BAD_REQUEST, "E4001", "재고가 부족합니다"),
    INVALID_ORDER_STATUS(HttpStatus.BAD_REQUEST, "E4002", "잘못된 주문 상태 변경입니다"),

    // 인증/인가
    UNAUTHORIZED(HttpStatus.UNAUTHORIZED, "E4010", "인증이 필요합니다"),
    INVALID_CREDENTIALS(HttpStatus.UNAUTHORIZED, "E4011", "이메일 또는 비밀번호가 올바르지 않습니다"),
    INVALID_TOKEN(HttpStatus.UNAUTHORIZED, "E4012", "유효하지 않은 토큰입니다"),
    ACCESS_DENIED(HttpStatus.FORBIDDEN, "E4030", "접근 권한이 없습니다"),

    // 공통
    INVALID_INPUT(HttpStatus.BAD_REQUEST, "E4000", "입력값이 올바르지 않습니다"),
    INTERNAL_SERVER_ERROR(HttpStatus.INTERNAL_SERVER_ERROR, "E5000", "서버 내부 오류가 발생했습니다");

    private final HttpStatus httpStatus;
    private final String code;
    private final String message;

    ErrorCode(HttpStatus httpStatus, String code, String message) {
        this.httpStatus = httpStatus;
        this.code = code;
        this.message = message;
    }

    public HttpStatus getHttpStatus() {
        return httpStatus;
    }

    public String getCode() {
        return code;
    }

    public String getMessage() {
        return message;
    }
}
