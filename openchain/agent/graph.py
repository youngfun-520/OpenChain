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
    node_steering_inject,
    node_finalize_followup,
    route_after_model,
)


def build_graph():
    """Build the LangGraph workflow."""
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("receive_input", node_receive_input)
    workflow.add_node("load_session_context", node_load_session_context)
    workflow.add_node("steering_inject", node_steering_inject)
    workflow.add_node("call_model", node_call_model)
    workflow.add_node("execute_tools", node_execute_tools)
    workflow.add_node("save_message_node", node_save_message_node)
    workflow.add_node("handle_error", node_handle_error)
    workflow.add_node("final_response", node_final_response)
    workflow.add_node("finalize_followup", node_finalize_followup)

    # Edges
    workflow.set_entry_point("receive_input")
    workflow.add_edge("receive_input", "load_session_context")
    workflow.add_edge("load_session_context", "steering_inject")
    workflow.add_edge("steering_inject", "call_model")

    workflow.add_conditional_edges(
        "call_model",
        route_after_model,
        {
            "execute_tools": "execute_tools",
            "handle_error": "handle_error",
            "final_response": "final_response"
        }
    )

    workflow.add_edge("execute_tools", "save_message_node")
    workflow.add_edge("save_message_node", END)

    workflow.add_edge("final_response", "finalize_followup")
    workflow.add_edge("finalize_followup", "save_message_node")
    workflow.add_edge("save_message_node", END)

    workflow.add_edge("handle_error", "call_model")

    return workflow.compile()