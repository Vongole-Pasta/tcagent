# 🚀 TcAgent 로컬 및 서버 배포 가이드 (Deployment Guide)

이 문서는 TcAgent 프로젝트를 **로컬 PC에서 기동하는 방법**과 **서버 배포용 브랜치에 푸시하기 전에 확인 및 수정해야 하는 설정**을 정리한 가이드라인입니다.

---

## 💻 1. 로컬 PC 기동 방법 (Local Development Guide)

로컬 개발 환경에서는 Docker Compose를 이용하여 모든 인프라 서비스(PostgreSQL, Neo4j, Nginx, pgAdmin) 및 애플리케이션 컨테이너를 한 번에 기동할 수 있습니다.

### ① 사전 요구사항 (Prerequisites)
- **Docker Desktop** 설치 및 실행 상태
- **Git** (소스코드 클론용)

### ② 환경 변수 설정
프로젝트 루트 디렉토리에 `.env` 파일을 작성합니다. 기동에 필수적인 기본 템플릿은 다음과 같습니다. (`.env.example` 파일을 복사하여 작성 가능)

```bash
# .env 파일 생성 및 값 설정
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password              # Neo4j 접속 비밀번호

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=tcagent
POSTGRES_USER=postgres
POSTGRES_PASSWORD=rhkswp!123         # PostgreSQL 접속 비밀번호

# AI 분석용 OpenAI API 키 (필수)
OPENAI_API_KEY=sk-proj-xxxx...       # 실제 OpenAI API 키 입력
```

### ③ 컨테이너 빌드 및 실행
Nginx 역프록시를 포함하여 전체 스택을 실행합니다. 루트 디렉토리에서 다음 명령어를 실행합니다.

```powershell
# 전체 서비스 빌드 및 백그라운드 실행
docker-compose up -d --build
```

실행 완료 후 아래 주소를 통해 각 서비스에 접근할 수 있습니다:
- **웹 서비스 (프론트엔드)**: `http://localhost/` (포트 80)
- **pgAdmin (PostgreSQL 웹 콘솔)**: `http://localhost:5050/` (ID: `admin@tcagent.com` / PW: `admin`)
- **Neo4j Browser (그래프 DB 콘솔)**: `http://localhost:7474/` (ID: `neo4j` / PW: `rhkswp!123`)

### ④ 개별 컨테이너 제어
코드 수정 후 특정 서비스만 다시 빌드하거나 재시작하고자 할 때 유용한 명령어 목록입니다.

```powershell
# 백엔드만 다시 빌드 및 반영
docker-compose up -d --build backend

# 프론트엔드만 다시 빌드 및 반영
docker-compose up -d --build frontend

# 특정 컨테이너 로그 실시간 모니터링
docker-compose logs -f backend
docker-compose logs -f frontend

# 전체 컨테이너 중지 (볼륨 데이터 보존)
docker-compose down
```

---

## 🔒 2. 서버 푸시 전 체크리스트 (Pre-push Settings Checklist)

운영 및 스테이징 서버에 코드를 올리기 위해 배포 브랜치에 `push`하기 전, 보안 및 환경 불일치 방지를 위해 다음 설정을 반드시 확인해야 합니다.

### ⬜ ① 중요 환경 변수 및 자격 증명 제거
- **주의**: API 키나 데이터베이스 비밀번호가 코드나 설정 파일 내에 하드코딩되지 않았는지 확인합니다.
- `.env` 파일은 `.gitignore`에 등록되어 있으므로 Git 저장소에 커밋되지 않아야 합니다. `.env.dev` 등 임시 개발용 파일 내에 실서버 키가 포함되지 않았는지 점검하세요.

### ⬜ ② Nginx 도메인 및 SSL 설정 확인 (`nginx.conf`)
- `nginx.conf` 파일의 `server_name`이 로컬호스트 외에 실제 서버 IP 또는 정규 도메인 주소로 설정되어 있는지 점검합니다.
  ```nginx
  server {
      listen 80;
      server_name 20.214.104.68; # 실서버의 IP 또는 도메인 명으로 매핑
      ...
  }
  ```
- **HTTPS 연동 (SSL/TLS)**: 실서버 환경에서 HTTPS를 사용하는 경우, 주석 처리된 `listen 443 ssl` 설정을 활성화하고 실서버 인증서 경로를 마운트해야 합니다.

### ⬜ ③ API 주소의 상대 경로 설정 유지 (`Dockerfile.frontend`)
- 프론트엔드의 `NEXT_PUBLIC_API_URL`은 로컬호스트나 실서버 IP로 고정(Hardcoding)하지 않고, 반드시 **상대 경로(`/api`)**로 유지해야 합니다.
  ```dockerfile
  # Dockerfile.frontend
  ENV NEXT_PUBLIC_API_URL=/api
  ```
- 이렇게 설정되어 있어야 브라우저가 클라이언트 접속 호스트(IP/도메인)를 기반으로 백엔드 API 서버를 동적으로 탐색합니다.

### ⬜ ④ 임시 테스트 데이터 생성 방지 (`api/main.py`)
- 로컬 테스트용 가상 사용자(`init_mock_user` 등) 기입 루틴이 백엔드 구동 lifespan에서 호출되지 않도록 방지합니다.
- 현재 백엔드 시작 시 개발자 정보 자동 Seed 기능은 정상적으로 완전히 제거되었습니다. 향후 추가적인 Mock DML 테스트 코드를 적용할 때도 `lifespan` 내에 포함되어 커밋되지 않도록 확인해 주세요.

### ⬜ ⑤ CORS 정책 점검 (`api/main.py`)
- 현재 백엔드의 CORS 정책은 `allow_origins=["*"]`로 모든 오리진의 허용을 지원하고 있습니다.
- 사내 보안 가이드라인에 따라 운영 배포 시 특정 신뢰할 수 있는 도메인 주소만 화이트리스트 처리하도록 제한 설정하는 것을 권장합니다.
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["http://20.214.104.68", "http://yourdomain.com"], # 예시
      ...
  )
  ```
