from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import tests, uploads, projects, graph
from core.analysis.analyzer import Analyzer
from core.agent.graph import create_agent_graph
from infra.db_client import DBClient
import logging

# 앱 진입점에서 로깅 초기화 (모든 모듈에 적용)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Global Instance
analyzer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global analyzer
    
    # Initialize Shared Components
    db_client = DBClient()
    analyzer = Analyzer(db_client)
    
    # Initialize Agent Graph
    agent_graph = create_agent_graph(db_client)

    
    # Inject into app state for access in routes
    app.state.analyzer = analyzer
    app.state.db_client = db_client
    app.state.agent_graph = agent_graph
    
    logger.info("✅ Analyzer Initialized")
    logger.info("✅ Integrated Test Agent Graph Initialized")
    
    yield
    db_client.close()

app = FastAPI(title="TcAgent (Java Code Analysis)", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routes
app.include_router(uploads.router)
app.include_router(projects.router)
app.include_router(graph.router)
app.include_router(tests.router)

@app.get("/")
async def root():
    return {"message": "TcAgent is running. Java Analysis Ready."}

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """처리되지 않은 예외를 잡아 일관된 에러 응답을 반환합니다."""
    from fastapi.responses import JSONResponse
    logger.error(f"처리되지 않은 오류: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "서버 내부 오류가 발생했습니다."}
    )
