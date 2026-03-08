package com.shopone.domain.notification.controller;

import com.shopone.domain.notification.dto.NotificationRequest;
import com.shopone.domain.notification.service.NotificationService;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

/**
 * 알림 REST 컨트롤러.
 *
 * [API 엣지 #12] SseEmitter — Spring MVC의 SSE 지원
 *   → Flux와 달리 SseEmitter는 전통적인 Servlet 기반 SSE
 *   → 파서가 SseEmitter를 리턴 타입으로 추출하지만, 이것이 SSE 스트림이라는 것을 알 수 없음
 */
@RestController
@RequestMapping("/api/notifications")
public class NotificationController {

    private final NotificationService notificationService;

    public NotificationController(NotificationService notificationService) {
        this.notificationService = notificationService;
    }

    /**
     * SSE 구독
     * GET /api/notifications/subscribe?memberId=...
     *
     * [API 엣지 #12] SseEmitter + TEXT_EVENT_STREAM
     */
    @GetMapping(value = "/subscribe", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter subscribe(@RequestParam Long memberId) {
        return notificationService.createEmitter(memberId);
    }

    /**
     * 알림 발송
     * POST /api/notifications/send
     */
    @PostMapping("/send")
    public ResponseEntity<Void> sendNotification(@RequestBody NotificationRequest request) {
        notificationService.sendBulk(request.memberIds(), request.message());
        return ResponseEntity.ok().build();
    }
}
