
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