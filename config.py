import os
from dotenv import load_dotenv

# Load environment variables based on APP_ENV (default: dev)
import sys

app_env = os.getenv("APP_ENV", "dev")
#app_env = os.getenv("APP_ENV", "prd")
env_file = f".env.{app_env}"

# Fallback to .env if specific file doesn't exist, or just load it
if os.path.exists(env_file):
    print(f"Loading configuration from {env_file}")
    load_dotenv(env_file)
else:
    print(f"Warning: {env_file} not found. Loading default .env")
    load_dotenv()

class Config:
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
    
    TARGET_DIR = os.getenv("TARGET_DIR", ".")
    
    # 제외할 디렉토리 및 파일 확장자
    EXCLUDED_DIRS = {".git", "node_modules", "dist", "build", "__pycache__", ".next", ".idea", ".vscode", "uploads_repository"}
    
    # JAVA ONLY
    ALLOWED_EXTENSIONS = {
        ".java": "java",
    }
