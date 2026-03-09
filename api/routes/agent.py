from fastapi import APIRouter, HTTPException, Request

from core.agent.happy_case.graph import HappyCaseAgentGraph

router = APIRouter(prefix="/agent", tags=["agent"])

@router.get("/happy-case/batch")
async def get_happy_case_scenarios(request: Request, method_ids: str = None):
    """
    지정된 메서드를 취합하여 Happy Case(200 OK) 시나리오를 일괄 생성합니다.
    (메서드가 엔드포인트인 경우와 서비스 레이어인 경우를 모두 지원)
    """
    analyzer = getattr(request.app.state, "analyzer", None)
    if not analyzer:
        raise HTTPException(status_code=503, detail="Analysis Agent not initialized")

    try:
        # 1. 대상 메서드 결정
        if method_ids:
            target_ids = [m_id.strip() for m_id in method_ids.split(",") if m_id.strip()]
        else:
            # 변경된 메서드들 찾기
            query = "MATCH (m:METHOD) WHERE m.status = 'MODIFIED' RETURN elementId(m) as id"
            records = analyzer.connector.execute_query(query)
            target_ids = [r["id"] for r in records]

        if not target_ids:
            return {"message": "No target methods found.", "scenarios": []}

        # 2. HappyCaseAgent 실행
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Generating happy-case scenarios for {len(target_ids)} methods...")
        
        agent = HappyCaseAgentGraph(analyzer.connector)
        result = agent.run(source_method_ids=target_ids)
        
        return {
            "source_method_count": len(target_ids),
            "scenarios": result.get("scenarios", []),
            "errors": result.get("errors", [])
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"Error in happy-case generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
