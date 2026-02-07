# TcAgent (Java Code Analysis)

자바 코드의 구조와 흐름을 분석하고 시각화하는 에이전트 시스템입니다.

## 📦 사전 요구사항 (Prerequisites)
- **Python 3.12+** (패키지 매니저로 `uv` 권장)
- **Node.js 18+** (Frontend 실행용)
- **Neo4j Database** (데이터 저장소)

## 🚀 시작하기 (Getting Started)

### 1. 데이터베이스 준비 (Neo4j)
Neo4j 인스턴스가 실행 중이어야 합니다.

### 2. 프로젝트 설정 (Configuration)
이 프로젝트는 **로컬 개발환경(dev)**과 **운영 환경(prd)**을 구분하여 설정 파일을 관리합니다.

#### 환경 설정 파일 준비
프로젝트 루트에 다음 두 파일을 생성해야 합니다.

**1) 로컬 개발용 (.env.dev)**
개인 로컬 Neo4j 설정을 입력하세요.
```ini
# .env.dev
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

**2) 운영/클라우드용 (.env.prd)**
팀원들과 공유된 클라우드 Neo4j 설정을 입력하세요.
```ini
# .env.prd
NEO4J_URI=bolt://<cloud-neo4j-uri>:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<secure-password>
```

### 3. 백엔드 실행 (Backend)
FastAPI 서버를 실행합니다.

```bash
# 1. 의존성 및 가상환경 동기화 (최초 1회 실행)
uv sync

# 2. 서버 실행
# 개발 환경 (로컬 DB 사용, 기본값)
APP_ENV=dev uv run uvicorn api.main:app --reload

# 운영 환경 (클라우드 DB 사용)
APP_ENV=prd uv run uvicorn api.main:app --reload
```
> **Tip**: `APP_ENV` 변수를 생략하면 기본적으로 `dev` 환경으로 실행됩니다.

- Swagger UI 문서: [http://localhost:8000/docs](http://localhost:8000/docs)

### 4. 프론트엔드 실행 (Frontend)
Next.js 웹 애플리케이션을 실행합니다.

```bash
cd frontend

# 1. 의존성 설치
npm install

# 2. 개발 서버 시작 (http://localhost:3000)
npm run dev
```

## 🔍 주요 기능 (Features)
- **Java 소스 분석**: `.zip` 파일 업로드 시 자동 분석 (AST 파싱)
- **증분 분석 (Incremental)**: 변경 사항을 감지하여 `NEW`(신규), `MODIFIED`(수정), `DELETED`(삭제) 상태 표시
- **호출 그래프 (Call Graph)**: 메서드 간 호출 관계 및 API 엔드포인트 연결 시각화
- **대시보드**: 프로젝트 전체 통계 및 분석 현황 요약