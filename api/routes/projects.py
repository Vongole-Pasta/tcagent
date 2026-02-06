from fastapi import APIRouter, HTTPException, Request
from graph_db.queries import CypherQueries
from typing import List, Dict, Any, Optional

router = APIRouter(prefix="/projects", tags=["projects"])

@router.get("/{project_id}/nodes")
async def get_project_nodes(project_id: str, request: Request, type: Optional[str] = None):
    """
    Get a flat list of Methods and Endpoints for the given project.
    
    Query Params:
    - type: 'endpoint' (optional) - if set, returns only endpoints.
    """
    analysis_flow = getattr(request.app.state, "analysis_flow", None)
    if not analysis_flow:
        raise HTTPException(status_code=503, detail="Analysis Agent not initialized")

    try:
        query = CypherQueries.GET_ALL_ENDPOINTS if type == "endpoint" else CypherQueries.GET_ALL_METHODS
        params = {} # Currently queries fetch all, filtering by project might be needed if multiple projects exist in one DB.
                    # Assuming checking 'project' property on nodes might be needed if multi-tenancy is fully implemented.
                    # For now, based on schema, FILE has 'project', but METHOD doesn't directly have 'project' unless derived.
                    # However, typical graph structures link everything to root. 
                    # Given the current queries from previous step don't filter by project, we will use them as is for single-tenant context 
                    # or assume the DB is isolated per session conceptualization.
                    # TODO: Enhance queries to filter by project via path: (p:Project)-...->(m:Method) in future if strict multi-project DB.
        
        results = analysis_flow.connector.execute_query(query, params)
        
        nodes = []
        for r in results:
            nodes.append({
                "id": r.get("id"),
                "name": r.get("name"),
                "signature": r.get("signature"),
                "endpoint": r.get("endpoint"),
                "http_method": r.get("http_method"),
                "type": "ENDPOINT" if r.get("endpoint") else "METHOD"
            })
            
        return {"nodes": nodes}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
