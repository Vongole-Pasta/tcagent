package com.shopone.global.exception;

/**
 * 비즈니스 로직 예외.
 * ErrorCode를 포함하여 GlobalExceptionHandler에서 일관된 에러 응답 생성.
 *
 * [파서 한계 #1] extends RuntimeException — 상속 관계 미감지
 * [API 엣지 #5] @ResponseStatus — 파서가 예외 클래스의 응답 상태코드를 추출하지 못함
 */
public class BusinessException extends RuntimeException {

    private final ErrorCode errorCode;

    public BusinessException(ErrorCode errorCode) {
        super(errorCode.getMessage());
        this.errorCode = errorCode;
    }

    public BusinessException(ErrorCode errorCode, String detailMessage) {
        super(detailMessage);
        this.errorCode = errorCode;
    }

    public ErrorCode getErrorCode() {
        return errorCode;
    }
}
