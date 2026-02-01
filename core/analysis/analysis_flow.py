import logging
import os
from core.analysis.skills.diff_checker import DiffChecker
from core.analysis.skills.incremental_analysis import IncrementalAnalyzer
from infra.db_client import DBClient

logger = logging.getLogger(__name__)

class AnalysisFlow:
    """
    파일 업로드, 변경 감지, 증분 분석을 담당하는 Flow입니다.
    기존 UnifiedCodeAnalysisAgent의 분석 역할을 수행합니다.
    """
    def __init__(self, connector: DBClient = None):
        self.connector = connector if connector else DBClient()
        
        # Initialize Sub-components
        self.change_detector = DiffChecker(self.connector)
        self.incremental_analyzer = IncrementalAnalyzer(self.connector)
        
    def scan_files(self, file_paths: list[str] = None, project: str = None):
        """
        1단계: 파일 스캔 및 분석 (Disk-based legacy method, kept for compatibility if needed)
        """
        logger.info(f"Starting Scan & Analysis Flow (Project: {project})...")
        
        # 1. Detect Changes
        if file_paths:
             changes = self.change_detector.detect_changes(file_paths)
        else:
             changes = []
        
        # 2. Incremental Update (Graph Sync)
        # Disk-based analysis is deprecated. Only memory-based analysis is supported via /upload endpoint.
        
        return {
            "changes": changes,
            "methods": [],
            "graph": self.fetch_project_graph(project)
        }

    def fetch_project_graph(self, project: str):
        """UI 시각화를 위한 프로젝트 그래프 데이터를 조회합니다."""
        if not project:
            return {"nodes": [], "edges": []}
            
        # Limit to prevent UI crash
        q = """
        MATCH (f:FILE {project: $project})
        OPTIONAL MATCH (f)-[r:AST|CONTAINS|DEFINES]->(n)
        RETURN f, r, n LIMIT 300
        """
        res = self.connector.execute_query(q, {"project": project})
        return self._format_graph_response(res)

    def _format_graph_response(self, results):
        """그래프 데이터를 UI 표준 포맷(Node/Edge)으로 변환합니다."""
        nodes = {}
        edges = {}
        
        for row in results:
            for key, val in row.items():
                if hasattr(val, 'labels'): # Node
                    nid = val.element_id
                    nodes[nid] = {
                        "id": nid,
                        "label": val.get("name") or val.get("id") or "Unknown",
                        "group": list(val.labels)[0] if val.labels else "Unknown",
                        # "title": str(dict(val))
                    }
                elif hasattr(val, 'type'): # Relationship
                    eid = val.element_id
                    edges[eid] = {
                        "id": eid,
                        "from": val.start_node.element_id,
                        "to": val.end_node.element_id,
                        "label": val.type
                    }
        
        return {"nodes": list(nodes.values()), "edges": list(edges.values())}
