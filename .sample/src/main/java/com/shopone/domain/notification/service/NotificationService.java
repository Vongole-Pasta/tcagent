package com.shopone.domain.notification.service;

import com.shopone.domain.member.entity.Member;
import com.shopone.domain.order.entity.Order;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 알림 서비스.
 * SSE(Server-Sent Events) 기반 실시간 알림 발송 담당.
 *
 * [파서 한계 #9] @Service — Spring 스테레오타입 미감지
 * [파서 한계 #10] 생성자 주입 — @Autowired 해석 불가 (여기서는 필드 없으므로 해당 없음)
 * [파서 커버] 메서드 시그니처, 필드 타입(Map<Long, SseEmitter>)
 */
@Service
public class NotificationService {

    private static final Logger log = LoggerFactory.getLogger(NotificationService.class);

    // SSE 연결 관리
    private final Map<Long, SseEmitter> emitters = new ConcurrentHashMap<>();

    /**
     * SSE 연결 생성
     */
    public SseEmitter createEmitter(Long memberId) {
        SseEmitter emitter = new SseEmitter(60_000L);
        emitters.put(memberId, emitter);
        emitter.onCompletion(() -> emitters.remove(memberId));
        emitter.onTimeout(() -> emitters.remove(memberId));
        return emitter;
    }

    /**
     * 회원 가입 환영 알림 발송
     */
    public void sendWelcome(Member member) {
        log.info("환영 알림 발송: {}", member.getEmail());
        sendToMember(member.getId(), "환영합니다, " + member.getFullName() + "님!");
    }

    /**
     * 주문 확인 알림 발송
     */
    public void sendOrderConfirmation(Order order) {
        log.info("주문 확인 알림: 주문 #{}", order.getId());
        sendToMember(order.getMember().getId(),
                "주문 #" + order.getId() + "이 접수되었습니다.");
    }

    /**
     * 다수 회원에게 일괄 알림 발송
     */
    public void sendBulk(List<Long> memberIds, String message) {
        for (Long memberId : memberIds) {
            sendToMember(memberId, message);
        }
    }

    private void sendToMember(Long memberId, String message) {
        SseEmitter emitter = emitters.get(memberId);
        if (emitter != null) {
            try {
                emitter.send(SseEmitter.event().name("notification").data(message));
            } catch (IOException e) {
                emitters.remove(memberId);
                log.warn("알림 발송 실패: memberId={}", memberId, e);
            }
        }
    }
}
