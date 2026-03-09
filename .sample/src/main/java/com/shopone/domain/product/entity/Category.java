package com.shopone.domain.product.entity;

import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.OneToMany;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;

/**
 * 상품 카테고리 (자기 참조 계층 구조).
 *
 * [파서 한계 #8] List<Category> children — 제네릭 필드에서 자기 참조 타입
 * [파서 커버] @ManyToOne, @OneToMany 관계 필드 추출
 */
@Entity
@Table(name = "categories")
@Getter
@NoArgsConstructor
public class Category {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String name;

    @ManyToOne
    private Category parent;

    @OneToMany(mappedBy = "parent")
    private List<Category> children = new ArrayList<>();

    public Category(String name, Category parent) {
        this.name = name;
        this.parent = parent;
    }

    public String getFullPath() {
        if (parent == null) {
            return name;
        }
        return parent.getFullPath() + " > " + name;
    }
}
