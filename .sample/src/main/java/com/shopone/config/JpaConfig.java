package com.shopone.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.data.jpa.repository.config.EnableJpaAuditing;

/**
 * JPA Auditing 설정.
 * BaseEntity의 @CreatedDate, @LastModifiedDate 자동 설정을 활성화한다.
 */
@Configuration
@EnableJpaAuditing
public class JpaConfig {
}
