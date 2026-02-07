# TcAgent (Java Code Analysis)

자바 코드의 구조와 흐름을 분석하고 시각화하는 에이전트 시스템입니다.

## 📦 사전 요구사항 (Prerequisites)
- **Python 3.12+** (패키지 매니저로 `uv` 권장)
- **Node.js 18+** (Frontend 실행용)
- **Neo4j Database** (데이터 저장소)

## 🚀 시작하기 (Getting Started)

### 1. 데이터베이스 준비 (Neo4j)
Neo4j 인스턴스가 실행 중이어야 합니다. (Docker 또는 Desktop 권장)

```bash
# Docker 실행 예시
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

### 2. 프로젝트 설정 (Configuration)
프로젝트 루트에 `.env` 파일을 생성하고 접속 정보를 입력하세요.

```ini
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
APP_ENV=dev
```

### 3. 백엔드 실행 (Backend)
FastAPI 서버를 실행합니다.

```bash
# 1. 의존성 동기화
uv sync

# 2. 서버 시작 (http://localhost:8000)
uv run uvicorn api.main:app --reload
```
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