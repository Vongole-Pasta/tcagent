from fastapi import APIRouter, HTTPException, Request
from graph_db.queries import CypherQueries
from typing import Dict, Any

router = APIRouter(prefix="/graph", tags=["graph"])

def process_path_result(results):
    """
    Helper to convert Neo4j path results into cytoscape/react-flow friendly Nodes & Edges
    """
    nodes = {}
    edges = {}
    
    for row in results:
        # Build metadata map for this row if provided
        metadata_list = row.get('metadata', [])
        metadata_map = {item['id']: item.get('className') for item in metadata_list if item and 'id' in item}

        path = row.get('path')
        if path is None:
            continue
            
        # Extract nodes and relationships from path
        # A path is a sequence of Node, Relationship, Node...
        for node in path.nodes:
            # element_id is the new standard ID in Neo4j 5
            node_id = node.element_id
            if node_id not in nodes:
                # Determine type based on labels
                labels = list(node.labels)
                node_type = "METHOD"
                if "EXTERNAL_CALL" in labels:
                    node_type = "EXTERNAL_CALL"
                elif node.get('endpoint_uri'):
                    node_type = "ENDPOINT"

                # Basic info
                node_data = {
                    "id": node_id,
                    "labels": labels,
                    "name": node.get('name', 'Unknown'),
                    "signature": node.get('signature', ''),
                    "endpoint": node.get('endpoint_uri'),
                    "http_method": node.get('http_method'),
                    "type": node_type,
                    "className": metadata_map.get(node_id) # Add className
                }
                nodes[node_id] = node_data
        
        for rel in path.relationships:
            rel_id = rel.element_id
            if rel_id not in edges:
                edges[rel_id] = {
                    "id": rel_id,
                    "source": rel.start_node.element_id,
                    "target": rel.end_node.element_id,
                    "type": rel.type
                }
            
    return {
        "nodes": list(nodes.values()),
        "edges": list(edges.values())
    }

def process_single_node(results):
    """
    Helper to convert single node result into 1-node graph
    """
    if not results:
        return {"nodes": [], "edges": []}
    
    row = results[0]
    node = row.get('m')
    class_name = row.get('className')
    
    if not node:
        return {"nodes": [], "edges": []}
        
    node_id = node.element_id
    labels = list(node.labels)
    node_type = "METHOD"
    if "EXTERNAL_CALL" in labels:
        node_type = "EXTERNAL_CALL"
    elif node.get('endpoint_uri'):
        node_type = "ENDPOINT"

    node_data = {
        "id": node_id,
        "labels": labels,
        "name": node.get('name', 'Unknown'),
        "signature": node.get('signature', ''),
        "endpoint": node.get('endpoint_uri'),
        "http_method": node.get('http_method'),
        "type": node_type,
        "className": class_name
    }
    
    return {
        "nodes": [node_data],
        "edges": []
    }

@router.get("/upstream/{method_id}")
async def get_upstream_graph(method_id: str, request: Request):
    """
    Get graph of upstream callers (Who calls me?)
    """
    analyzer = getattr(request.app.state, "analyzer", None)
    if not analyzer:
        raise HTTPException(status_code=503, detail="Analysis Agent not initialized")

    try:
        results = analyzer.connector.execute_query(
            CypherQueries.GET_UPSTREAM_IMPACT_FOR_FE, 
            {"method_id": method_id}
        )
        return process_path_result(results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/downstream/{method_id}")
async def get_downstream_graph(method_id: str, request: Request):
    """
    Get graph of downstream callees (Who do I call?)
    """
    analyzer = getattr(request.app.state, "analyzer", None)
    if not analyzer:
        raise HTTPException(status_code=503, detail="Analysis Agent not initialized")

    try:
        results = analyzer.connector.execute_query(
            CypherQueries.GET_DOWNSTREAM_FLOW_FOR_FE, 
            {"method_id": method_id}
        )
        return process_path_result(results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/node/{method_id}")
async def get_node_details(method_id: str, request: Request):
    """
    Get detailed information for a specific node (Source code, etc.)
    """
    analyzer = getattr(request.app.state, "analyzer", None)
    if not analyzer:
        raise HTTPException(status_code=503, detail="Analysis Agent not initialized")

    try:
        results = analyzer.connector.execute_query(
            CypherQueries.GET_METHOD_CONTEXT, 
            {"method_id": method_id}
        )
        
        if not results:
            raise HTTPException(status_code=404, detail="Node not found")
            
        node = results[0]
        return {
            "name": node.get("name"),
            "signature": node.get("signature"),
            "source": node.get("source"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
