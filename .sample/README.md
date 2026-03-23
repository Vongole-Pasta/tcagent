# ShopOne — 파서 테스트용 Spring Boot 샘플 애플리케이션

Java 소스코드 파서(JavaParser + EdgeLinker)의 커버리지와 한계점을 검증하기 위한 종합 테스트 픽스처.
이커머스(ShopOne) 도메인으로 구성되며, 실제 서비스와 유사한 구조를 갖는다.

## 기술 스택

| 항목 | 버전/선택 |
|---|---|
| Java | 17 |
| Spring Boot | 3.2.4 |
| 빌드 도구 | Gradle (Groovy DSL) |
| DB | H2 인메모리 (런타임/테스트 모두) |
| Lombok | 혼용 (Entity/Service는 Lombok, DTO(Record)는 직접 작성) |

## 기동 방법

### 애플리케이션 실행

H2 인메모리 DB를 사용하므로 별도의 DB 설치가 필요 없다.

```bash
cd .sample
./gradlew bootRun
```

서버가 `http://localhost:8080` 에서 시작된다.
H2 콘솔은 `http://localhost:8080/h2-console` 에서 접근 가능하다.

### 테스트 실행

```bash
cd .sample
./gradlew test
```

## 프로젝트 구조

```
.sample/
├── build.gradle
├── settings.gradle
├── docs/                              # 도메인별 API 엣지케이스 가이드
│   ├── 01-member-api.md
│   ├── 02-product-api.md
│   ├── 03-order-api.md
│   └── 04-notification-api.md
├── src/main/java/com/shopone/
│   ├── ShopOneApplication.java
│   ├── common/                        # 공통 응답, 기반 엔티티
│   │   ├── ApiResponse.java           #   제네릭 응답 래퍼 + 내부 Meta 클래스
│   │   ├── ApiResponseCode.java       #   커스텀 응답 코드 Enum
│   │   ├── BaseEntity.java            #   @MappedSuperclass (id, createdAt, updatedAt)
│   │   └── PagedResponse.java         #   페이징 응답 Record
│   ├── config/                        # Spring 설정
│   │   ├── AsyncConfig.java           #   @EnableAsync + ThreadPoolTaskExecutor
│   │   ├── JpaConfig.java             #   @EnableJpaAuditing
│   │   └── WebMvcConfig.java          #   ArgumentResolver, Interceptor 등록
│   ├── domain/
│   │   ├── member/                    # 회원 도메인
│   │   │   ├── controller/
│   │   │   │   └── MemberController.java    # 8개 엔드포인트
│   │   │   ├── dto/
│   │   │   │   ├── MemberCreateRequest.java # Record + Validation
│   │   │   │   └── MemberResponse.java      # Record + static factory
│   │   │   ├── entity/
│   │   │   │   ├── Member.java              # extends BaseEntity, Lombok
│   │   │   │   ├── MemberGrade.java         # Enum (BRONZE/SILVER/GOLD/VIP)
│   │   │   │   └── Address.java             # @Embeddable
│   │   │   ├── repository/
│   │   │   │   └── MemberRepository.java    # extends JpaRepository
│   │   │   └── service/
│   │   │       └── MemberService.java       # 오버로딩, 메서드 레퍼런스, var
│   │   ├── product/                   # 상품 도메인
│   │   │   ├── controller/
│   │   │   │   ├── ProductController.java       # 6개 엔드포인트
│   │   │   │   └── ProductSearchController.java # 3개 엔드포인트
│   │   │   ├── dto/
│   │   │   │   └── ProductDto.java          # 내부 클래스 (Create, Update, Response)
│   │   │   ├── entity/
│   │   │   │   ├── Product.java             # 내부 Builder 클래스
│   │   │   │   └── Category.java            # 자기참조 계층구조
│   │   │   ├── repository/
│   │   │   │   ├── ProductRepository.java
│   │   │   │   └── CategoryRepository.java
│   │   │   └── service/
│   │   │       └── ProductService.java      # static import, Builder 패턴
│   │   ├── order/                     # 주문 도메인
│   │   │   ├── controller/
│   │   │   │   └── OrderController.java     # 7개 엔드포인트
│   │   │   ├── dto/
│   │   │   │   ├── OrderCreateRequest.java  # 중첩 Record
│   │   │   │   └── OrderResponse.java       # 중첩 Record
│   │   │   ├── entity/
│   │   │   │   ├── Order.java               # 내부 DeliveryInfo 클래스
│   │   │   │   ├── OrderItem.java           # 메서드 체이닝
│   │   │   │   └── OrderStatus.java         # 상태 전이 로직 Enum
│   │   │   ├── repository/
│   │   │   │   └── OrderRepository.java
│   │   │   └── service/
│   │   │       ├── OrderService.java        # Flux SSE, var, 생성자 호출
│   │   │       └── OrderValidator.java      # 오버로딩 validate() x2
│   │   └── notification/              # 알림 도메인
│   │       ├── controller/
│   │       │   └── NotificationController.java  # 2개 엔드포인트
│   │       ├── dto/
│   │       │   └── NotificationRequest.java
│   │       └── service/
│   │           └── NotificationService.java     # SseEmitter 관리
│   └── global/                        # 글로벌 인프라
│       ├── exception/
│       │   ├── ErrorCode.java               # Enum (HttpStatus + 코드 + 메시지)
│       │   ├── BusinessException.java       # extends RuntimeException
│       │   └── GlobalExceptionHandler.java  # @RestControllerAdvice
│       ├── filter/
│       │   └── RequestLoggingFilter.java    # implements Filter
│       ├── interceptor/
│       │   └── ApiVersionInterceptor.java   # implements HandlerInterceptor
│       └── resolver/
│           ├── CurrentMember.java           # 커스텀 어노테이션
│           └── CurrentMemberArgumentResolver.java
├── src/main/resources/
│   └── application.yml
└── src/test/
    ├── java/com/shopone/domain/
    │   ├── member/
    │   │   ├── controller/MemberControllerTest.java  # @WebMvcTest (5 tests)
    │   │   └── service/MemberServiceTest.java        # Mockito 단위 (5 tests)
    │   ├── product/
    │   │   └── service/ProductServiceTest.java       # Mockito 단위 (4 tests)
    │   └── order/
    │       └── service/OrderServiceTest.java         # Mockito 단위 (4 tests)
    └── resources/
        └── application-test.yml
```

**Java 파일**: 43개 (main) + 4개 (test) = 47개
**API 엔드포인트**: 26개 (5개 컨트롤러)

## 도메인 개요

| 도메인 | 컨트롤러 | 엔드포인트 | 설명 |
|---|---|---|---|
| 회원 (Member) | MemberController | 8개 | 회원 CRUD, 프로필 이미지, 주소, 인증 정보 조회 |
| 상품 (Product) | ProductController, ProductSearchController | 9개 | 상품 CRUD, 비동기 조회, 검색, HATEOAS |
| 주문 (Order) | OrderController | 7개 | 주문 생성/조회, 상태 변경, 리액티브, SSE, PDF |
| 알림 (Notification) | NotificationController | 2개 | SSE 구독, 일괄 알림 발송 |

## API 엣지케이스 문서

각 도메인별 엔드포인트의 curl 예시, 요청/응답 형태, 엣지케이스 설명은 `docs/` 디렉토리를 참고한다.

- [01-member-api.md](docs/01-member-api.md) — 회원 API (8개)
- [02-product-api.md](docs/02-product-api.md) — 상품 API (9개)
- [03-order-api.md](docs/03-order-api.md) — 주문 API (7개)
- [04-notification-api.md](docs/04-notification-api.md) — 알림 API (2개)
