-- 카테고리
INSERT INTO categories (id, name) VALUES (1, '전자기기');
INSERT INTO categories (id, name) VALUES (2, '식품');

-- 회원 (password: 모두 'password123'의 BCrypt 해시)
INSERT INTO members (id, email, first_name, last_name, password, grade, login_count, fail_count, active, created_at, updated_at)
VALUES (1, 'hong@example.com', '길동', '홍', '$2a$10$4xfSH2yF9QIpdo0VxOAofOxu3lRhtLDaJ6yCTlpGvZQm/ztHE9cwi', 'BRONZE', 0, 0, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

INSERT INTO members (id, email, first_name, last_name, password, grade, login_count, fail_count, active, created_at, updated_at)
VALUES (2, 'kim@example.com', '구매', '김', '$2a$10$4xfSH2yF9QIpdo0VxOAofOxu3lRhtLDaJ6yCTlpGvZQm/ztHE9cwi', 'GOLD', 5, 0, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

INSERT INTO members (id, email, first_name, last_name, password, grade, login_count, fail_count, active, created_at, updated_at)
VALUES (3, 'lee@example.com', '판매', '이', '$2a$10$4xfSH2yF9QIpdo0VxOAofOxu3lRhtLDaJ6yCTlpGvZQm/ztHE9cwi', 'SILVER', 3, 0, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

-- 회원 주소
INSERT INTO member_addresses (member_id, street, city, zip_code) VALUES (1, '강남대로 1', '서울', '06000');
INSERT INTO member_addresses (member_id, street, city, zip_code) VALUES (2, '판교역로 235', '성남', '13487');

-- 상품
INSERT INTO products (id, name, price, description, stock_quantity, active, category_id, created_at, updated_at)
VALUES (1, '노트북', 1500000, '고성능 노트북', 10, true, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

INSERT INTO products (id, name, price, description, stock_quantity, active, category_id, created_at, updated_at)
VALUES (2, '마우스', 35000, '무선 마우스', 100, true, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

INSERT INTO products (id, name, price, description, stock_quantity, active, category_id, created_at, updated_at)
VALUES (3, '빨간 티셔츠', 29000, 'L사이즈 빨간 티셔츠', 50, true, 2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

-- 주문 (member_id=1 홍길동, 노트북 2개 + 마우스 1개)
INSERT INTO orders (id, member_id, status, total_amount, recipient_name, phone, street, city, zip_code, created_at, updated_at)
VALUES (1, 1, 'PENDING', 3035000, '홍길동', '010-1234-5678', '강남대로 1', '서울', '06000', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

-- 주문 항목
INSERT INTO order_items (id, order_id, product_id, quantity, unit_price)
VALUES (1, 1, 1, 2, 1500000);
INSERT INTO order_items (id, order_id, product_id, quantity, unit_price)
VALUES (2, 1, 2, 1, 35000);

-- AUTO_INCREMENT 시퀀스 충돌 방지
ALTER TABLE categories ALTER COLUMN id RESTART WITH 100;
ALTER TABLE members ALTER COLUMN id RESTART WITH 100;
ALTER TABLE products ALTER COLUMN id RESTART WITH 100;
ALTER TABLE orders ALTER COLUMN id RESTART WITH 100;
ALTER TABLE order_items ALTER COLUMN id RESTART WITH 100;
