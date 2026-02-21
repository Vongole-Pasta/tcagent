import os
from pydantic_settings import BaseSettings
from typing import Set
from dotenv import load_dotenv

# 환경 변수를 통한 환경 설정 (기본값: dev)
app_env = os.getenv("APP_ENV", "dev")
env_file = f".env.{app_env}"

# 실제 OS 환경 변수에 .env 값을 주입 (LangSmith 등 외부 라이브러리가 자동 인식하도록)
if os.path.exists(env_file):
    load_dotenv(env_file, override=True)
else:
    load_dotenv(".env", override=True)

class Config(BaseSettings):
    """
    앱 설정을 관리하는 Pydantic BaseSettings 클래스.
    .env 파일에서 자동으로 환경변수를 읽어오며, 누락 시 기본값을 사용합니다.
    앱 시작 시 타입 유효성 검증이 자동으로 수행됩니다.
    """
    # Neo4j 연결 정보
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # 작업 대상 디렉토리
    TARGET_DIR: str = "."

    # LangSmith & LLM 설정
    LANGCHAIN_TRACING_V2: str = "true"
    LANGCHAIN_PROJECT: str = "tcagent-integrated-test"
    LANGCHAIN_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    MODEL_NAME: str = "gpt-4o"

    # 제외할 디렉토리 (클래스 변수, .env와 무관)
    EXCLUDED_DIRS: Set[str] = {".git", "node_modules", "dist", "build", "__pycache__", ".next", ".idea", ".vscode", "uploads_repository"}

    # 허용 확장자 (Java Only)
    ALLOWED_EXTENSIONS: dict = {".java": "java"}

    model_config = {
        "env_file": env_file if os.path.exists(env_file) else ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",  # .env에 추가 변수가 있어도 무시
    }

# 싱글톤 인스턴스 (전역에서 Config 속성 접근용)
_config = Config()

# 기존 코드 호환성을 위해 클래스 레벨 접근도 가능하게 유지
# 사용법: from config import Config → Config.NEO4J_URI 등
class _ConfigCompat:
    """기존 코드와의 호환성을 위한 래퍼 (Config.XXX 형태 접근 지원)"""
    def __getattr__(self, name):
        return getattr(_config, name)

Config = _ConfigCompat()
