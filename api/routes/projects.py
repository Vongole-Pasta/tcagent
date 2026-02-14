from fastapi import APIRouter, HTTPException, Request
from graph_db.queries import CypherQueries
from typing import List, Dict, Any, Optional

router = APIRouter(prefix="/projects", tags=["projects"])

@router.get("/")
async def get_all_projects(request: Request):
    """
    Get a list of all available projects.
    """
    analyzer = getattr(request.app.state, "analyzer", None)
    if not analyzer:
        raise HTTPException(status_code=503, detail="Analysis Agent not initialized")

    try:
        # Fetch distinct projects from FILE nodes
        query = "MATCH (f:FILE) RETURN DISTINCT f.project as project"
        results = analyzer.connector.execute_query(query)
        projects = [r["project"] for r in results if r.get("project")]
        return {"projects": projects}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{project_id}/nodes")
async def get_project_nodes(project_id: str, request: Request, type: Optional[str] = None):
    """
    Get a flat list of Methods and Endpoints for the given project.
    
    Query Params:
    - type: 'endpoint' (optional) - if set, returns only endpoints.
    """
    analyzer = getattr(request.app.state, "analyzer", None)
    if not analyzer:
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
        
        results = analyzer.connector.execute_query(query, params)
        
        nodes = []
        for r in results:
            # Determine status
            status = r.get("status") # Direct status (Methods)
            statuses = r.get("statuses") # Aggregated status list (Endpoints)
            
            # Identify effective status for endpoints
            if statuses:
                # Normalize check for variations
                normalized = set(s.upper().replace("-", "") for s in statuses if s)
                
                # Priority: DELETED > NEW > MODIFIED > AS-IS
                if "DELETED" in normalized:
                    status = "DELETED"
                elif "NEW" in normalized:
                    status = "NEW"
                elif "MODIFIED" in normalized or "TOBE" in normalized:
                    status = "MODIFIED"
                elif "ASIS" in normalized:
                    status = "AS-IS"
            
            nodes.append({
                "id": r.get("id"),
                "name": r.get("name"),
                "signature": r.get("signature"),
                "endpoint": r.get("endpoint"),
                "http_method": r.get("http_method"),
                "type": "ENDPOINT" if r.get("endpoint") else "METHOD",
                "status": status,
                "className": r.get("class_name")
            })
            
        return {"nodes": nodes}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
