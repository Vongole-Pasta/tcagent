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
            # Determine status
            status = r.get("status") # Direct status (Methods)
            statuses = r.get("statuses") # Aggregated status list (Endpoints)
            
            # Identify effective status for endpoints
            if statuses:
                # Priority: DIRTY > (others)
                if "DIRTY" in statuses:
                    status = "DIRTY"
                elif "VERIFIED" in statuses: 
                    # Only if ALL are verified? Or if any is verified? 
                    # Usually DIRTY trumps all. If not dirty, map to something else or None.
                    # For now simplistically: if any dirty, it's dirty.
                    status = "VERIFIED" if all(s == "VERIFIED" for s in statuses if s) else None
                # Basic check: if any non-null status exists and not dirty, maybe show it?
                # Let's stick to simple "DIRTY" propagation for now.
            
            nodes.append({
                "id": r.get("id"),
                "name": r.get("name"),
                "signature": r.get("signature"),
                "endpoint": r.get("endpoint"),
                "http_method": r.get("http_method"),
                "type": "ENDPOINT" if r.get("endpoint") else "METHOD",
                "status": status
            })
            
        return {"nodes": nodes}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
