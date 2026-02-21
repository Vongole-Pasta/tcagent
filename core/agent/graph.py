
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from infra.db_client import DBClient
from core.agent.state import AgentState
from core.agent.nodes import IntegratedTestAgentNodes

def create_agent_graph(db_client: DBClient):
    """
    통합 테스트 에이전트를 위한 LangGraph 워크플로우를 생성하고 컴파일합니다.
    """
    nodes = IntegratedTestAgentNodes(db_client)
    
    workflow = StateGraph(AgentState)
    
    # Add Nodes
    workflow.add_node("identify_targets", nodes.identify_targets)
    workflow.add_node("trace_roots", nodes.trace_roots)
    workflow.add_node("extract_payloads", nodes.extract_payloads)
    workflow.add_node("synthesize_strategy", nodes.synthesize_strategy)
    workflow.add_node("generate_scenarios", nodes.generate_scenarios)
    workflow.add_node("evaluate_scenarios", nodes.evaluate_scenarios)
    
    # Define Edges
    workflow.set_entry_point("identify_targets")
    
    # Conditional logic or direct sequence
    workflow.add_edge("identify_targets", "trace_roots")
    workflow.add_edge("trace_roots", "extract_payloads")
    workflow.add_edge("extract_payloads", "generate_scenarios")
    workflow.add_edge("generate_scenarios", "evaluate_scenarios")
    workflow.add_edge("synthesize_strategy", END)

    def should_retry(state: AgentState):
        """피드백에 기반하여 트레이스 재생성이 필요한지 확인합니다."""
        for ctx in state.test_contexts:
            # 평가 실패 AND 재시도 횟수 제한 미만인 경우
            if not ctx.evaluation_passed and ctx.retry_count < 2:
                return "retry"
        return "end"

    workflow.add_conditional_edges(
        "evaluate_scenarios",
        should_retry,
        {
            "retry": "generate_scenarios",
            "end": "synthesize_strategy"
        }
    )
    
    # 체크포인터용 메모리 컴파일 (선택 사항, 디버깅에 유용)
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    
    return app
