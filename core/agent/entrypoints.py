import os
from core.agent.happy_case.graph import HappyCaseAgentGraph
from graph_db.client import DBClient

# DBClient 인스턴스화 (Config 클래스에서 자동으로 설정 로드)
db_client = DBClient()

# HappyCaseAgentGraph 인스턴스화 및 그래프 객체 노출
happy_case_agent = HappyCaseAgentGraph(db_client)
happy_case_graph = happy_case_agent.graph
