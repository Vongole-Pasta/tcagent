package com.shopone.domain.member.entity;

import com.shopone.common.BaseEntity;
import jakarta.persistence.CascadeType;
import jakarta.persistence.CollectionTable;
import jakarta.persistence.Column;
import jakarta.persistence.ElementCollection;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.OneToMany;
import jakarta.persistence.Table;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import lombok.Getter;

import java.util.ArrayList;
import java.util.List;

/**
 * 회원 엔티티.
 *
 * [파서 한계 #1] extends BaseEntity — 상속 관계 미감지
 * [파서 한계 #2] this.validate() — this 키워드 해석 불가 → EXTERNAL_CALL로 처리됨
 * [파서 한계 #8] List<Address> addresses — 제네릭 필드의 타입 파라미터 해석 한계
 * [파서 한계 #14] var fullName = ... — var 타입 추론 무시
 * [파서 한계 #15] String[] tags — 배열 차원 정보 소실
 * [파서 커버] Lombok @Getter 혼용, 다중 선언자(loginCount, failCount), @NotBlank 등 필드 어노테이션
 */
@Entity
@Table(name = "members")
@Getter
public class Member extends BaseEntity {

    @NotBlank
    @Email
    @Column(unique = true, nullable = false)
    private String email;

    @NotBlank
    private String firstName;

    @NotBlank
    private String lastName;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private MemberGrade grade = MemberGrade.BRONZE;

    @ElementCollection
    @CollectionTable(name = "member_addresses", joinColumns = @JoinColumn(name = "member_id"))
    private List<Address> addresses = new ArrayList<>();

    // [파서 한계 #15] 배열 차원 정보가 소실됨 (String[] → String 으로 처리)
    @ElementCollection
    @CollectionTable(name = "member_tags", joinColumns = @JoinColumn(name = "member_id"))
    @Column(name = "tag")
    private List<String> tags = new ArrayList<>();

    // [파서 커버] 다중 선언자 — int loginCount, failCount;
    private int loginCount, failCount;

    private boolean active = true;

    protected Member() {
    }

    public Member(String email, String firstName, String lastName) {
        this.email = email;
        this.firstName = firstName;
        this.lastName = lastName;
    }

    /**
     * [파서 한계 #14] var 타입추론 — 파서가 var의 실제 타입을 알 수 없음
     */
    public String getFullName() {
        var fullName = firstName + " " + lastName;
        return fullName;
    }

    /**
     * [파서 한계 #2] this.validate() — this 키워드가 EXTERNAL_CALL이 됨
     */
    public void upgradeGrade(int totalPurchaseAmount) {
        this.validate();
        this.grade = MemberGrade.fromAmount(totalPurchaseAmount);
    }

    public void addAddress(Address address) {
        this.addresses.add(address);
    }

    public void updateAddress(Address newAddress) {
        this.addresses.clear();
        this.addresses.add(newAddress);
    }

    public void recordLogin() {
        this.loginCount++;
        this.failCount = 0;
    }

    public void recordLoginFailure() {
        this.failCount++;
        if (this.failCount >= 5) {
            this.active = false;
        }
    }

    public boolean isActive() {
        return active;
    }

    /**
     * this.validate()의 대상 메서드 — 파서가 this 호출을 해석하지 못하므로 연결 안 됨
     */
    private void validate() {
        if (email == null || email.isBlank()) {
            throw new IllegalStateException("이메일이 비어있습니다");
        }
    }
}
