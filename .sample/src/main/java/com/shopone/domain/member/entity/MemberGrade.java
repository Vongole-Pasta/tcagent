package com.shopone.domain.member.entity;

/**
 * 회원 등급 열거형.
 *
 * [파서 커버] Enum 상수 추출 + 다중 인자 생성자
 */
public enum MemberGrade {

    BRONZE("B", 0, 0.0),
    SILVER("S", 1000, 0.02),
    GOLD("G", 5000, 0.05),
    VIP("V", 10000, 0.10);

    private final String code;
    private final int threshold;
    private final double discountRate;

    MemberGrade(String code, int threshold, double discountRate) {
        this.code = code;
        this.threshold = threshold;
        this.discountRate = discountRate;
    }

    public String getCode() {
        return code;
    }

    public int getThreshold() {
        return threshold;
    }

    public double getDiscountRate() {
        return discountRate;
    }

    /**
     * 누적 구매금액에 해당하는 등급 반환
     */
    public static MemberGrade fromAmount(int totalAmount) {
        MemberGrade result = BRONZE;
        for (MemberGrade grade : values()) {
            if (totalAmount >= grade.threshold) {
                result = grade;
            }
        }
        return result;
    }
}
