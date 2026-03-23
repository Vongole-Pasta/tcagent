package com.shopone.domain.member.entity;

import jakarta.persistence.Embeddable;

/**
 * 주소 값 객체 (Embeddable).
 *
 * [파서 커버] 단순 클래스, 필드 추출, @Embeddable 어노테이션
 */
@Embeddable
public class Address {

    private String street;
    private String city;
    private String zipCode;

    protected Address() {
    }

    public Address(String street, String city, String zipCode) {
        this.street = street;
        this.city = city;
        this.zipCode = zipCode;
    }

    public String getStreet() {
        return street;
    }

    public String getCity() {
        return city;
    }

    public String getZipCode() {
        return zipCode;
    }

    public String toFullAddress() {
        return String.format("%s %s (%s)", city, street, zipCode);
    }
}
