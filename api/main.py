from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import uploads, projects, graph, agent, auth
from core.analysis.analyzer import Analyzer
from graph_db.client import DBClient
from infra.postgres import PostgresClient
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
    
    # Initialize PostgreSQL Client
    pg_client = PostgresClient()
        
    # Inject into app state for access in routes
    app.state.analyzer = analyzer
    app.state.pg_client = pg_client
    
    logger.info("✅ Analyzer & PostgreSQL Client Initialized")
    
    yield
    db_client.close()
    pg_client.close()

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
app.include_router(agent.router)
app.include_router(auth.router)

@app.get("/")
async def root():
    return {"message": "TcAgent is running. Java Analysis Ready."}
