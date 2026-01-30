# TcAgent (Total Code Agent)

**TcAgent**는 대규모 코드베이스의 구조와 호출 흐름을 분석하고 그래프 데이터베이스(Neo4j)에 시각화 가능한 형태로 저장하는 에이전트입니다.
현재 **Java** 언어 분석에 특화되어 있습니다.

## Features

- **Java 코드 파싱**: Tree-sitter를 사용하여 Java 소스 코드를 정밀 분석
- **증분 분석**: 변경된 파일만 감지하여 그래프 DB 업데이트
- **호출 그래프**: 메서드 간 호출 관계, 제어 흐름 추적
- **FastAPI 서버**: REST API를 통한 파일 업로드 및 분석 요청 처리

## Requirements

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (Package Manager)
- Neo4j Database (Locally installed or AuraDB)

## Installation & Setup

### 1. `uv` 설치

#### Windows (Powershell)
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### macOS / Linux
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. 프로젝트 셋팅

```bash
# 프로젝트 의존성 설치
uv sync
```

### 3. 환경 변수 설정
`.env` 파일을 생성하고 Neo4j 접속 정보를 입력하세요.

```ini
NEO4J_URI=neo4j://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=my_password
```

### 4. 서버 실행

#### Windows / macOS Common
```bash
uv run uvicorn api.main:app --reload
```

## API Usage

- **Upload & Analyze**: `POST /upload`
- **Swagger UI**: `http://localhost:8000/docs`