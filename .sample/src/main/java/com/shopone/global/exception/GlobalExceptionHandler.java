package com.shopone.global.exception;

import com.shopone.common.ApiResponse;
import com.shopone.common.ApiResponseCode;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.HashMap;
import java.util.Map;

/**
 * 전역 예외 처리기.
 *
 * [API 엣지 #4] @ControllerAdvice + @ExceptionHandler — 모든 컨트롤러의 에러 응답을 여기서 조작
 *   → 컨트롤러 함수만 보고는 에러 응답 형태를 알 수 없음
 * [파서 한계 #11] @RestControllerAdvice — 파서가 의미적으로 감지하지 못함
 * [파서 한계 #12] @ResponseStatus(HttpStatus.BAD_REQUEST) — 파서가 응답 상태코드를 추출하지 못함
 * [파서 한계 #3] e.getBindingResult().getFieldErrors() — 메서드 체이닝 끊김
 * [파서 한계 #7] error -> errors.put(...) — 람다 파라미터 타입 미지
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    /**
     * 비즈니스 예외 처리: ErrorCode에 정의된 HTTP 상태코드와 메시지로 응답
     */
    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ApiResponse<Void>> handleBusinessException(BusinessException e) {
        ErrorCode errorCode = e.getErrorCode();
        return ResponseEntity
                .status(errorCode.getHttpStatus())
                .body(ApiResponse.error(ApiResponseCode.BAD_REQUEST, errorCode.getMessage()));
    }

    /**
     * @Valid 유효성 검증 실패 처리
     *
     * [파서 한계 #12] @ResponseStatus — 파서가 이 어노테이션을 해석하지 못함
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiResponse<Map<String, String>> handleValidationException(MethodArgumentNotValidException e) {
        Map<String, String> errors = new HashMap<>();
        e.getBindingResult().getFieldErrors()
                .forEach(error -> errors.put(error.getField(), error.getDefaultMessage()));
        return ApiResponse.error(ApiResponseCode.BAD_REQUEST, errors.toString());
    }

    /**
     * 기타 예외 처리
     */
    @ExceptionHandler(Exception.class)
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public ApiResponse<Void> handleException(Exception e) {
        return ApiResponse.error(ApiResponseCode.INTERNAL_ERROR, e.getMessage());
    }
}
