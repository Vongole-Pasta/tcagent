from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import uploads, projects, graph
from core.analysis.skills.incremental_analysis import IncrementalAnalyzer
from infra.db_client import DBClient
import logging

logger = logging.getLogger(__name__)

# Global Instance
incremental_analyzer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global incremental_analyzer
    
    # Initialize Shared Components
    db_client = DBClient()
    incremental_analyzer = IncrementalAnalyzer(db_client)
    
    # Inject into app state for access in routes
    app.state.incremental_analyzer = incremental_analyzer
    
    logger.info("✅ IncrementalAnalyzer Initialized")
    
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

@app.get("/")
async def root():
    return {"message": "TcAgent is running. Java Analysis Ready."}
