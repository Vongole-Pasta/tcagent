
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from core.agent.state import GeneratedScenario

router = APIRouter(prefix="/api/tests", tags=["Integrated Tests"])

class GenerateRequest(BaseModel):
    project_id: str = "default"

@router.post("/generate")
async def generate_tests(request: Request, body: GenerateRequest):
    """
    Trigger the integrated test agent workflow.
    """
    agent_graph = request.app.state.agent_graph
    
    if not agent_graph:
        raise HTTPException(status_code=500, detail="Agent graph not initialized")
    
    # 에이전트 그래프 실행
    try:
        # 초기 상태
        initial_input = {"target_methods": [], "trace_results": [], "generated_scenarios": []}
        
        # 비동기 실행 (LLM 호출이 포함되어 있어 블로킹 방지)
        import asyncio
        config = {"configurable": {"thread_id": "default_thread"}}
        loop = asyncio.get_event_loop()
        final_state = await loop.run_in_executor(
            None, lambda: agent_graph.invoke(initial_input, config=config)
        )
        
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
