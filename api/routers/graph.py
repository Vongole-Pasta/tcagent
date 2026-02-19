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
        path = row.get('path')
        metadata = row.get('metadata', []) # Check for metadata
        # Handle metadata which defaults to list of dicts from collect()
        # Create map from id -> className
        metadata_map = {}
        if metadata:
            for m in metadata:
                if m and isinstance(m, dict):
                     metadata_map[m.get('id')] = m.get('className')

        if not path:
            continue
            
        # Extract nodes and relationships from path
        # A path is a sequence of Node, Relationship, Node...
        for node in path.nodes:
            # element_id is the new standard ID in Neo4j 5
            node_id = node.element_id
            if node_id not in nodes:
                # Basic info
                node_data = {
                    "id": node_id,
                    "labels": list(node.labels),
                    "name": node.get('name', 'Unknown'),
                    "signature": node.get('signature', ''),
                    "endpoint": node.get('endpoint'),
                    "http_method": node.get('http_method'),
                    "type": "ENDPOINT" if node.get('endpoint') else "METHOD",
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
    node_data = {
        "id": node_id,
        "labels": list(node.labels),
        "name": node.get('name', 'Unknown'),
        "signature": node.get('signature', ''),
        "endpoint": node.get('endpoint'),
        "http_method": node.get('http_method'),
        "type": "ENDPOINT" if node.get('endpoint') else "METHOD",
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
            CypherQueries.GET_UPSTREAM_IMPACT, 
            {"method_id": method_id}
        )
        
        # If no results (empty list), try to fetch the single node
        processed_graph = process_path_result(results)
        
        # If no nodes found (either no results or path processing yielded 0 nodes), try fallback
        if not processed_graph['nodes']:
            single_node_results = analyzer.connector.execute_query(
                CypherQueries.GET_NODE_METADATA,
                {"method_id": method_id}
            )
            return process_single_node(single_node_results)
            
        return processed_graph
    except Exception as e:
        import traceback
        traceback.print_exc()
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
            CypherQueries.GET_DOWNSTREAM_FLOW, 
            {"method_id": method_id}
        )
        
        processed_graph = process_path_result(results)
        
        # If no nodes found, try fallback
        if not processed_graph['nodes']:
            single_node_results = analyzer.connector.execute_query(
                CypherQueries.GET_NODE_METADATA,
                {"method_id": method_id}
            )
            return process_single_node(single_node_results)
            
        return processed_graph
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
