package com.shopone.domain.notification.dto;

import java.util.List;

/**
 * 알림 발송 요청 DTO (Record).
 */
public record NotificationRequest(
        List<Long> memberIds,
        String message
) {
}
