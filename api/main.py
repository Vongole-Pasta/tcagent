from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import uploads, projects, graph
from api.routers import tests
from core.analysis.analyzer import Analyzer
from core.agent.graph import create_agent_graph
from infra.db_client import DBClient
import logging

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
