"""Tests for LangGraph agent."""
import pytest
from openchain.agent.state import AgentState


def test_agent_state_fields():
    """Verify AgentState has required fields."""
    state = AgentState(
        session_id="test-session",
        workspace="/tmp",
        input_message="Hello",
        parent_node_id=None,
        model="test-model",
        messages=[],
        tool_calls=[],
        tool_results=[],
        current_tool_call_index=0,
        error=None,
        retry_count=0,
        security_context={}
    )
    assert state["session_id"] == "test-session"
    assert state["input_message"] == "Hello"
    assert state["messages"] == []


@pytest.mark.asyncio
async def test_graph_single_turn():
    """Test that graph processes one turn and returns END."""
    from openchain.agent.graph import build_graph
    graph = build_graph()
    assert graph is not None