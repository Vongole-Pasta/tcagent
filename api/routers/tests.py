
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
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

@router.post("/download")
async def download_tests(body: DownloadRequest):
    """
    생성된 시나리오(JSON)를 Excel 파일로 변환하여 다운로드합니다.
    응답 전송 후 임시 파일은 자동으로 삭제됩니다.
    """
    import logging
    logger = logging.getLogger("api.routers.tests")
    logger.info(f"다운로드 요청 수신: {len(body.scenarios)}개 시나리오")
    logger.info(f"요약 길이: {len(body.strategy_summary) if body.strategy_summary else 0}")
    
    file_path = None
    try:
        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            file_path = tmp.name
        
        ExcelExporter.create_workbook(body.scenarios, body.strategy_summary, file_path)
        
        # 응답 전송 후 임시 파일 자동 삭제
        def cleanup(path: str):
            if os.path.exists(path):
                os.unlink(path)
        
        return FileResponse(
            path=file_path, 
            filename="integrated_tests.xlsx",
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            background=BackgroundTask(cleanup, file_path)
        )
        
    except Exception as e:
        # 에러 발생 시 임시 파일 정리
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
        raise HTTPException(status_code=500, detail=str(e))
