package com.shopone.domain.member.repository;

import com.shopone.domain.member.entity.Member;
import com.shopone.domain.member.entity.MemberGrade;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

/**
 * 회원 리포지토리 인터페이스.
 *
 * [파서 한계 #1] extends JpaRepository<Member, Long> — 상속/구현 관계 미감지
 * [파서 커버] 인터페이스 추출, 메서드 시그니처(리턴 타입 + 파라미터), 제네릭
 */
public interface MemberRepository extends JpaRepository<Member, Long> {

    Optional<Member> findByEmail(String email);

    List<Member> findByGrade(MemberGrade grade);

    boolean existsByEmail(String email);

    Page<Member> findByFirstNameContainingOrLastNameContaining(
            String firstName, String lastName, Pageable pageable);

    List<Member> findByActiveTrue();
}
