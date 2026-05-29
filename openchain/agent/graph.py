"""LangGraph workflow definition."""
from langgraph.graph import StateGraph, END
from openchain.agent.state import AgentState
from openchain.agent.nodes import (
    node_receive_input,
    node_load_session_context,
    node_call_model,
    node_execute_tools,
    node_save_message_node,
    node_handle_error,
    node_final_response,
    route_after_model,
)


def build_graph():
    """Build the LangGraph workflow."""
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("receive_input", node_receive_input)
    workflow.add_node("load_session_context", node_load_session_context)
    workflow.add_node("call_model", node_call_model)
    workflow.add_node("execute_tools", node_execute_tools)
    workflow.add_node("save_message_node", node_save_message_node)
    workflow.add_node("handle_error", node_handle_error)
    workflow.add_node("final_response", node_final_response)

    # Edges
    workflow.set_entry_point("receive_input")
    workflow.add_edge("receive_input", "load_session_context")
    workflow.add_edge("load_session_context", "call_model")

    workflow.add_conditional_edges(
        "call_model",
        route_after_model,
        {
            "execute_tools": "execute_tools",
            "final_response": "final_response"
        }
    )

    workflow.add_edge("execute_tools", "save_message_node")
    workflow.add_edge("save_message_node", END)

    workflow.add_edge("final_response", "save_message_node")
    workflow.add_edge("save_message_node", END)

    workflow.add_edge("handle_error", "call_model")

    return workflow.compile()