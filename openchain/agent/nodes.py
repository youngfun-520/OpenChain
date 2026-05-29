"""LangGraph node implementations."""
from typing import Literal
from openchain.agent.state import AgentState
from openchain.session import SessionManager


async def node_receive_input(state: AgentState) -> AgentState:
    """Receive user input and create a user message."""
    from langchain_core.messages import HumanMessage
    return {
        **state,
        "messages": state["messages"] + [HumanMessage(content=state["input_message"])]
    }


async def node_load_session_context(state: AgentState) -> AgentState:
    """Load session history into messages list."""
    sm = SessionManager()
    await sm.initialize()
    nodes = await sm.get_session_nodes(state["session_id"])
    from langchain_core.messages import HumanMessage, AIMessage
    messages = []
    for node in nodes:
        if node["role"] == "user":
            messages.append(HumanMessage(content=node["content"]))
        elif node["role"] == "assistant":
            messages.append(AIMessage(content=node["content"]))
    return {**state, "messages": messages}


async def node_call_model(state: AgentState) -> AgentState:
    """Call LLM with current messages and tools."""
    from openchain.model_registry import ModelRegistry
    from langchain_anthropic import ChatAnthropic

    mr = ModelRegistry()
    mr.validate_model_config(state["model"])
    llm = ChatAnthropic(model=state["model"])
    result = await llm.ainvoke(state["messages"])
    return {
        **state,
        "messages": state["messages"] + [result]
    }


async def node_execute_tools(state: AgentState) -> AgentState:
    """Execute pending tool calls and collect results."""
    import uuid
    tool_calls = state.get("tool_calls", [])
    tool_results = []
    for i, tc in enumerate(tool_calls):
        if i < state["current_tool_call_index"]:
            continue
        tool_results.append({
            "tool_call_id": tc.get("id", str(uuid.uuid4())),
            "tool_name": tc.get("name", "unknown"),
            "result": {"status": "mock", "message": "mock tool result"}
        })
    return {
        **state,
        "tool_results": tool_results,
        "current_tool_call_index": len(tool_calls)
    }


async def node_save_message_node(state: AgentState) -> AgentState:
    """Save assistant response to message_nodes table."""
    sm = SessionManager()
    await sm.initialize()
    last_message = state["messages"][-1] if state["messages"] else None
    if last_message:
        await sm.save_assistant_message_node(
            session_id=state["session_id"],
            parent_node_id=state.get("parent_node_id"),
            content=last_message.content,
            tool_calls=state.get("tool_calls"),
            tool_results=state.get("tool_results"),
            model=state["model"]
        )
    await sm.close()
    return state


async def node_handle_error(state: AgentState) -> AgentState:
    """Handle errors and decide retry or abort."""
    new_retry_count = state.get("retry_count", 0) + 1
    if new_retry_count >= 3:
        return {**state, "error": None, "retry_count": new_retry_count}
    return {**state, "error": None, "retry_count": new_retry_count}


async def node_final_response(state: AgentState) -> AgentState:
    """Output final response (END state)."""
    return state


def route_after_model(state: AgentState) -> Literal["execute_tools", "final_response"]:
    """Route based on whether model returned tool calls."""
    last_message = state["messages"][-1] if state["messages"] else None
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "execute_tools"
    return "final_response"