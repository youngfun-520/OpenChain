"""Tests for LangGraph error routing to handle_error node."""
import pytest
from openchain.agent.state import AgentState
from openchain.agent.graph import build_graph, route_after_model

@pytest.mark.asyncio
async def test_error_node_reachable_when_llm_fails():
    """Test that graph routes to handle_error when call_model sets error."""
    graph = build_graph()
    assert graph is not None

    # When error is set, should route to handle_error
    error_state = AgentState(
        session_id="test",
        workspace="/tmp",
        input_message="hello",
        parent_node_id=None,
        model="test",
        messages=[],
        tool_calls=[],
        tool_results=[],
        current_tool_call_index=0,
        error="API key invalid",
        retry_count=0,
        security_context={}
    )
    route = route_after_model(error_state)
    assert route == "handle_error", f"Expected handle_error, got {route}"

    # When no error, should route based on tool_calls
    clean_state = AgentState(
        session_id="test",
        workspace="/tmp",
        input_message="hello",
        parent_node_id=None,
        model="test",
        messages=[],
        tool_calls=[{"name": "read_file", "args": {"path": "/tmp/foo"}}],
        tool_results=[],
        current_tool_call_index=0,
        error=None,
        retry_count=0,
        security_context={}
    )
    route2 = route_after_model(clean_state)
    assert route2 == "execute_tools", f"Expected execute_tools, got {route2}"

@pytest.mark.asyncio
async def test_execute_tools_sets_error_on_security_failure():
    """Test that node_execute_tools sets error field for security violations."""
    from openchain.agent.nodes import node_execute_tools

    state = AgentState(
        session_id="test-session",
        workspace="/tmp",
        input_message="test",
        parent_node_id=None,
        model="test",
        messages=[],
        tool_calls=[{"name": "bash", "args": {"command": "rm -rf /"}}],
        tool_results=[],
        current_tool_call_index=0,
        error=None,
        retry_count=0,
        security_context={}
    )

    result = await node_execute_tools(state)
    assert result.get("error") is not None

@pytest.mark.asyncio
async def test_handle_error_increments_retry_count():
    """Test that handle_error node increments retry_count and clears error."""
    from openchain.agent.nodes import node_handle_error

    state = AgentState(
        session_id="test",
        workspace="/tmp",
        input_message="hello",
        parent_node_id=None,
        model="test",
        messages=[],
        tool_calls=[],
        tool_results=[],
        current_tool_call_index=0,
        error="Some error",
        retry_count=0,
        security_context={}
    )

    result = await node_handle_error(state)
    assert result["retry_count"] == 1
    assert result["error"] is None  # error cleared for retry

@pytest.mark.asyncio
async def test_handle_error_max_retries_gives_up():
    """Test that handle_error gives up after 3 retries."""
    from openchain.agent.nodes import node_handle_error

    state = AgentState(
        session_id="test",
        workspace="/tmp",
        input_message="hello",
        parent_node_id=None,
        model="test",
        messages=[],
        tool_calls=[],
        tool_results=[],
        current_tool_call_index=0,
        error="Some error",
        retry_count=3,  # already at max
        security_context={}
    )

    result = await node_handle_error(state)
    assert result.get("error") == "Max retries exceeded"
    assert result["retry_count"] == 3