
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from infra.db_client import DBClient
from core.agent.state import AgentState
from core.agent.nodes import IntegratedTestAgentNodes

def create_agent_graph(db_client: DBClient):
    """
    Create and compile the LangGraph workflow for the Integrated Test Agent.
    """
    nodes = IntegratedTestAgentNodes(db_client)
    
    workflow = StateGraph(AgentState)
    
    # Add Nodes
    workflow.add_node("identify_targets", nodes.identify_targets)
    workflow.add_node("trace_roots", nodes.trace_roots)
    workflow.add_node("generate_scenarios", nodes.generate_scenarios)
    
    # Define Edges
    workflow.set_entry_point("identify_targets")
    
    # Conditional logic or direct sequence
    workflow.add_edge("identify_targets", "trace_roots")
    workflow.add_edge("trace_roots", "generate_scenarios")
    workflow.add_edge("generate_scenarios", END)
    
    # Compile with memory for checkpointer (optional, good for debugging)
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    
    return app
