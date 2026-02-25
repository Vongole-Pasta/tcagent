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

## 🏗 백엔드 및 파서 폴더 구조 (Backend & Parser Directory Structure)
- `api/`: FastAPI 진입점(`main.py`) 및 전역 라우터 설정, API 엔드포인트를 관리합니다.
- `core/`: 프로젝트의 핵심 비즈니스 로직 및 분석 엔진이 포함되어 있습니다.
  - `core/agent/`: LangGraph 기반의 지능형 에이전트로, 코드 변경 사항을 분석하여 테스트 시나리오를 구성합니다.
  - `core/analysis/`: 핵심 Java 파싱 및 분석 로직이 위치합니다.
    - `parser.py`: 소스 코드를 읽고 추상 구문 트리(AST) 수준으로 분해/파싱하는 역할을 담당합니다.
    - `analyzer.py`: 파싱된 구문을 순회하며 메서드, 클래스, 관계 등을 추출해 DB 구조로 변환합니다.
- `graph_db/`: Neo4j 그래프 데이터베이스의 스키마 정의(`schema.py`) 및 Cypher 쿼리(`queries.py`)를 관리합니다.
- `infra/`: 데이터베이스 연결(`db_client.py`) 등 외부 인프라스트럭처와의 통신 및 세션 관리를 담당합니다.

## 🤖 통합 테스트 에이전트 구조 (LangGraph Node Workflow)
현재 테스트 생성 에이전트는 애플리케이션의 코드 변경 사항을 감지하고, 실제 실행 가능한 테스트 시나리오를 설계하는 파이프라인으로 구성되어 있습니다.
1. **`identify_targets`**: DB에 기록된 코드 베이스에서 변경되었거나(`MODIFIED`) 새로 추가된(`NEW`) 대상 메서드를 식별합니다.
2. **`trace_roots`**: 식별된 대상 메서드로부터 시작하여 호출 계층을 거슬러 올라가, 최상위 진입점(예: Controller의 API 엔드포인트)을 역추적합니다. 이를 통해 루트부터 타겟까지의 테스트 컨텍스트를 구성합니다.
3. **`generate_scenarios`**: 타겟 메서드의 변경된 로직을 트리거할 수 있는 유효한 테스트 시나리오(예: 구체화된 `curl` 명령어 및 파라미터)를 LLM을 활용하여 생성합니다.
4. **`evaluate_scenarios`** (Critic Node): 생성된 시나리오가 실제 코드의 명세(URL, 파라미터 구조, HTTP 메서드 등)와 예상 결과(조건문, 반환값, 로그)에 사실적으로 부합하는지 엄격하게 평가합니다. 평가에 실패할 경우 피드백 루프를 통해 `generate_scenarios`로 돌아가 재시도합니다.