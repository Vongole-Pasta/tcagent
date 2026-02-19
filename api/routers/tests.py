
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import tempfile
import os

from core.agent.state import GeneratedScenario
from core.agent.excel_exporter import ExcelExporter

router = APIRouter(prefix="/api/tests", tags=["Integrated Tests"])

class GenerateRequest(BaseModel):
    project_id: str = "default"

class DownloadRequest(BaseModel):
    scenarios: List[GeneratedScenario]
    strategy_summary: Optional[str] = None

@router.post("/generate")
async def generate_tests(request: Request, body: GenerateRequest):
    """
    Trigger the integrated test agent workflow.
    """
    agent_graph = request.app.state.agent_graph
    
    if not agent_graph:
        raise HTTPException(status_code=500, detail="Agent graph not initialized")
    
    # Run the graph
    try:
        # Initial state
        initial_input = {"target_methods": [], "trace_results": [], "generated_scenarios": []}
        
        # Invoke the graph
        config = {"configurable": {"thread_id": "default_thread"}}
        final_state = agent_graph.invoke(initial_input, config=config)
        
        if isinstance(final_state, dict):
            scenarios = final_state.get("generated_scenarios", [])
            strategy_summary = final_state.get("test_strategy_summary", None)

        else:
            scenarios = getattr(final_state, "generated_scenarios", [])
            strategy_summary = getattr(final_state, "test_strategy_summary", None)

        
        return {
            "scenarios": scenarios,
            "strategy_summary": strategy_summary,
            "count": len(scenarios)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/download")
async def download_tests(body: DownloadRequest):
    """
    Convert the provided scenarios (JSON) into an Excel file.
    """
    import logging
    logger = logging.getLogger("api.routers.tests")
    logger.info(f"Received download request with {len(body.scenarios)} scenarios.")
    logger.info(f"Summary length: {len(body.strategy_summary) if body.strategy_summary else 0}")
    
    try:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            file_path = tmp.name
        
        ExcelExporter.create_workbook(body.scenarios, body.strategy_summary, file_path)
        
        # Return as file response
        return FileResponse(
            path=file_path, 
            filename="integrated_tests.xlsx",
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        if os.path.exists(file_path):
            os.unlink(file_path)
        raise HTTPException(status_code=500, detail=str(e))
