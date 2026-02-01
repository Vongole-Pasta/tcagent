import os
from dotenv import load_dotenv

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
