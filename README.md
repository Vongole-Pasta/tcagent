# 🚀 TcAgent (Java Code Analysis)

> **Java 소스 코드의 변경을 실시간으로 감지하고 구조를 시각화하며, 자동으로 테스트 시나리오를 설계하는 지능형 에이전트 시스템입니다.**

---

## ✨ 1. 주요 기능 (Features)

사용자는 TcAgent를 통해 다음과 같은 핵심 분석 기능들을 수행할 수 있습니다.

- **📦 간편한 소스 업로드**: `.zip` 파일 기반의 Java 프로젝트 소스 업로드 시 즉각적인 자동 분석(AST 파싱)이 진행됩니다.
- **🔍 증분 분석 (Incremental Analysis)**: 전체 코드가 아닌 변경된 사항만을 식별하여 `NEW`(신규), `MODIFIED`(수정), `DELETED`(삭제) 상태로 추적합니다.
- **🕸️ 지능형 호출 그래프 (Call Graph)**: 메서드 간의 호출 관계뿐만 아니라, Controller API 엔드포인트부터 깊은 비즈니스 로직까지의 흐름을 시각적으로 연결해 줍니다.
- **🤖 AI 테스트 시나리오 자동 생성**: 
  - LangGraph 기반의 에이전트가 변경된 메서드부터 최상단 API 진입점을 역추적(Trace)합니다.
  - LLM을 활용해 실제 엔드포인트에서 실행 가능한 HTTP 테스트 데이터(Happy Case 등)를 자동 생성하고 검증(Evaluate)합니다.
- **📊 한눈에 보는 대시보드**: 전체 프로젝트의 분석 통계와 코드 변경 현황을 직관적인 UI로 요약해서 보여줍니다.

---

## 🛠 2. 기술 스택 (Tech Stack)

### Backend & Agent
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-FF4F00?style=for-the-badge&logo=langchain&logoColor=white)

### Frontend
![NodeJS](https://img.shields.io/badge/Node.js-18+-339933?style=for-the-badge&logo=node.js&logoColor=white)
![NextJS](https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=next.js&logoColor=white)

### Database & Environment
![Neo4j](https://img.shields.io/badge/Neo4j-008CC1?style=for-the-badge&logo=neo4j&logoColor=white)
![uv](https://img.shields.io/badge/uv-Package_Manager-F5C211?style=for-the-badge)

---

## 🏁 3. 시작 가이드 (Getting Started)

로컬 환경에서 프로젝트를 실행하는 방법입니다.

### Prerequisites (사전 요구사항)
- **Python 3.12+** (속도 향상을 위해 패키지 매니저로 `uv` 권장)
- **Node.js 18+** (Frontend 실행용)
- **Neo4j** (데이터베이스, Docker 또는 Desktop 실행 권장)

### Configuration (환경 설정)
루트 경로에 로컬 개발용 `.env.dev` 파일을 생성하고 Neo4j 접속 정보를 입력합니다.
```ini
# .env.dev
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=my_secure_password
```

### Installation & Running (설치 및 실행)

**1. 백엔드 실행 (Backend)**
```bash
# 1. 의존성 동기화 (초기 1회)
uv sync

# 2. FastAPI 서버 실행 (기본 포트: 8000)
uv run uvicorn api.main:app --reload
```
> 실행 후 Swagger UI 문서 확인: [http://localhost:8000/docs](http://localhost:8000/docs)

**2. 프론트엔드 실행 (Frontend)**
```bash
cd frontend

# 1. npm 패키지 설치
npm install

# 2. Next.js 개발 서버 실행 (기본 포트: 3000)
npm run dev
```

---

## � 4. 프로젝트 구조 (Project Structure)

프로젝트를 다루기 위해 알아두어야 할 핵심 구조입니다.

```text
tcagent/
├── api/             # FastAPI 진입점(main.py) 및 RESTful 라우터(graph, agent 등) 모음
├── core/            # 핵심 비즈니스 로직 및 에이전트 시스템
│   ├── agent/       # LangGraph 기반 AI 에이전트 (Happy Case 테스트 생성 등)
│   └── analysis/    # Java 파일 AST 파싱 및 구조 분석 트리거
├── graph_db/        # Neo4j 스키마 및 Cypher Query 파일 통합 본부
├── infra/           # DB 클라이언트, 외부 통신 등 인프라스트럭처 연결 모듈
├── frontend/        # 코드 그래프 시각화 및 대시보드를 보여줄 Next.js 앱
├── langgraph.json   # 외부 LangGraph Studio 연동을 위한 메타데이터 파일
└── main.py          # 서버 구동, DB 초기화 등을 돕는 CLI 스크립트 진입점
```

---

## 🤝 5. 기여 방법 및 라이선스 (Contributing & License)

### Contributing
프로젝트에 기여해 주셔서 감사합니다! 버그 수정, 새 기능 제안 등 무엇이든 환영합니다.
1. 이 저장소를 Fork 합니다.
2. 새 기능 브랜치를 만듭니다. (`git checkout -b feature/amazing-feature`)
3. 작업 내역을 커밋합니다. (`git commit -m 'Add some amazing feature'`)
4. 브랜치에 푸시합니다. (`git push origin feature/amazing-feature`)
5. **Pull Request**를 생성해 주세요.

### License
이 프로젝트는 **MIT License** 조건 하에 배포됩니다. 자유롭게 사용, 변경 및 재배포가 가능합니다. 자세한 내용은 `LICENSE` 파일을 참고하세요.