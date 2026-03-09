import logging
from typing import List

from langgraph.graph import StateGraph, END
from langgraph.constants import Send

from core.agent.happy_case.state import HappyCaseState, WorkerState
from core.agent.happy_case.nodes import HappyCaseAgentNodes
from graph_db.client import DBClient

logger = logging.getLogger(__name__)

class HappyCaseAgentGraph:
    def __init__(self, db_client: DBClient):
        self.nodes = HappyCaseAgentNodes(db_client)
        self.graph = self._build_graph()

    def _build_graph(self):

        def continue_to_workers(state: HappyCaseState):
            """planner 종료 후 각 엔드포인트마다 독립적인 워커 서브 그래프를 병렬 실행합니다."""
            impact_groups = state.get("impact_groups", {})
            if not impact_groups:
                logger.warning("No impact groups found, skipping to END.")
                return []
            logger.info(f"Dispatching {len(impact_groups)} workers: {list(impact_groups.keys())}")
            return [
                Send("worker", {"group": group})
                for group in impact_groups.values()
            ]

        # --- 서브 그래프: 단일 엔드포인트 처리 (retriever -> generator) ---
        worker_builder = StateGraph(WorkerState)
        worker_builder.add_node("retriever", self.nodes.retriever_worker_node)
        worker_builder.add_node("generator", self.nodes.generator_worker_node)

        worker_builder.set_entry_point("retriever")
        worker_builder.add_edge("retriever", "generator")
        worker_builder.add_edge("generator", END)

        compiled_worker = worker_builder.compile()

        # --- 메인 그래프 ---
        workflow = StateGraph(HappyCaseState)
        workflow.add_node("planner", self.nodes.planner_node)
        workflow.add_node("worker", compiled_worker)
        workflow.add_node("formatter", self.nodes.formatter_node)

        workflow.set_entry_point("planner")
        workflow.add_conditional_edges("planner", continue_to_workers, ["worker"])
        workflow.add_edge("worker", "formatter")
        workflow.add_edge("formatter", END)

        return workflow.compile()

    def run(self, source_method_ids: List[str]):
        """
        에이전트를 실행하여 병렬로 Happy Case 시나리오를 생성합니다.
        """
        return self.graph.invoke({"source_method_ids": source_method_ids})
