package com.shopone.common;

import com.fasterxml.jackson.annotation.JsonInclude;

import java.time.Instant;
import java.util.UUID;

/**
 * 모든 API 응답을 감싸는 공통 래퍼.
 *
 * [API 엣지 #1] ResponseEntity<ApiResponse<T>> — 실제 응답 구조가 중첩 제네릭
 * [API 엣지 #2] ApiResponseCode 커스텀 코드 사용
 * [파서 한계 #4] 내부 클래스 Meta — 동명 타입 충돌 가능성 (다른 파일에도 Meta 존재 시)
 * [파서 커버] 내부 static 클래스 추출, 제네릭 필드, static 팩토리 메서드
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public class ApiResponse<T> {

    private ApiResponseCode code;
    private String message;
    private T data;
    private Meta meta;

    private ApiResponse() {
    }

    // 성공 응답 (데이터 포함)
    public static <T> ApiResponse<T> success(T data) {
        ApiResponse<T> response = new ApiResponse<>();
        response.code = ApiResponseCode.SUCCESS;
        response.message = ApiResponseCode.SUCCESS.getMessage();
        response.data = data;
        response.meta = Meta.now();
        return response;
    }

    // 성공 응답 (코드 지정)
    public static <T> ApiResponse<T> success(ApiResponseCode code, T data) {
        ApiResponse<T> response = new ApiResponse<>();
        response.code = code;
        response.message = code.getMessage();
        response.data = data;
        response.meta = Meta.now();
        return response;
    }

    // 에러 응답
    public static <T> ApiResponse<T> error(ApiResponseCode code, String message) {
        ApiResponse<T> response = new ApiResponse<>();
        response.code = code;
        response.message = message;
        response.meta = Meta.now();
        return response;
    }

    public ApiResponseCode getCode() {
        return code;
    }

    public String getMessage() {
        return message;
    }

    public T getData() {
        return data;
    }

    public Meta getMeta() {
        return meta;
    }

    /**
     * 응답 메타 정보.
     *
     * [파서 한계 #4] 내부 static 클래스 — 다른 파일의 동명 클래스와 충돌 가능
     */
    public static class Meta {
        private long timestamp;
        private String traceId;

        private Meta() {
        }

        public static Meta now() {
            Meta meta = new Meta();
            meta.timestamp = Instant.now().toEpochMilli();
            meta.traceId = UUID.randomUUID().toString().substring(0, 8);
            return meta;
        }

        public long getTimestamp() {
            return timestamp;
        }

        public String getTraceId() {
            return traceId;
        }
    }
}
