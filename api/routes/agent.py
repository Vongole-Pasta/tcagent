from fastapi import APIRouter, HTTPException, Request

from core.agent.integration_agent import IntegrationAgent
from core.agent.happy_case_agent import HappyCaseAgent

router = APIRouter(prefix="/agent", tags=["agent"])

@router.get("/integration-scenario/{method_id}")
async def get_integration_test_scenario(method_id: str, request: Request):
    """
    LangGraph 에이전트를 사용하여 특정 메서드 변경에 따른 고도화된 통합 테스트 시나리오를 생성합니다.
    """
    analyzer = getattr(request.app.state, "analyzer", None)
    if not analyzer:
        raise HTTPException(status_code=503, detail="Analysis Agent not initialized")

    try:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Generating scenario for method: {method_id}")

        agent = IntegrationAgent(analyzer.connector)
        # 단일 메서드 ID를 리스트로 감싸서 전달
        result = agent.run([method_id])
        return {
            "method_id": method_id,
            "scenarios": result.get("scenarios", []),
            "errors": result.get("errors", [])
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"Error in single scenario generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/integration-scenario/batch/all")
async def get_batch_integration_test_scenarios(request: Request, method_ids: str = None):
    """
    프로젝트 내 지정된 메서드 또는 모든 변경(MODIFIED)된 메서드들을 취합하여 일괄 시나리오를 생성합니다.
    """
    analyzer = getattr(request.app.state, "analyzer", None)
    if not analyzer:
        raise HTTPException(status_code=503, detail="Analysis Agent not initialized")

    try:
        # 1. 대상 메서드 결정
        if method_ids:
            target_ids = [m_id.strip() for m_id in method_ids.split(",") if m_id.strip()]
        else:
            # 1. 변경된 메서드들 찾기
            query = "MATCH (m:METHOD) WHERE m.status = 'MODIFIED' RETURN elementId(m) as id"
            records = analyzer.connector.execute_query(query)
            target_ids = [r["id"] for r in records]

        if not target_ids:
            return {"message": "No target methods found.", "scenarios": []}

        # 2. 에이전트 실행
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Analyzing {len(target_ids)} methods...")
        
        agent = IntegrationAgent(analyzer.connector)
        result = agent.run(target_ids)
        
        return {
            "source_method_count": len(target_ids),
            "scenarios": result.get("scenarios", []),
            "errors": result.get("errors", [])
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"Error in batch generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
        
        agent = HappyCaseAgent(analyzer.connector)
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
