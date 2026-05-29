"""Tests for message queue functionality."""
import pytest
import tempfile
import os


@pytest.mark.asyncio
async def test_queue_messages_column_exists():
    """sessions table should have queue_messages TEXT column."""
    from openchain.db import Database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        async with Database(db_path) as db:
            await db.initialize()
            cursor = await db.conn.execute("PRAGMA table_info(sessions)")
            columns = {row[1] for row in await cursor.fetchall()}
            assert "queue_messages" in columns


@pytest.mark.asyncio
async def test_steering_queue_methods():
    """SessionManager should have add/get/remove_steering_message methods."""
    from openchain.session import SessionManager
    sm = SessionManager()
    await sm.initialize()
    try:
        session = await sm.create_session(workspace="/tmp")
        sid = session["session_id"]
        # Add steering message
        result = await sm.add_steering_message(sid, "Be concise.", position=0)
        assert result["status"] == "success"
        # Get queue
        queue = await sm.get_steering_queue(sid)
        assert len(queue) == 1
        assert queue[0]["content"] == "Be concise."
        # Remove
        await sm.remove_steering_message(sid, queue[0]["id"])
        queue = await sm.get_steering_queue(sid)
        assert len(queue) == 0
    finally:
        await sm.close()


@pytest.mark.asyncio
async def test_followup_queue_methods():
    """SessionManager should have add/get/remove_followup_message methods."""
    from openchain.session import SessionManager
    sm = SessionManager()
    await sm.initialize()
    try:
        session = await sm.create_session(workspace="/tmp")
        sid = session["session_id"]
        result = await sm.add_followup_message(sid, "Want me to elaborate?")
        assert result["status"] == "success"
        queue = await sm.get_followup_queue(sid)
        assert len(queue) == 1
        assert queue[0]["content"] == "Want me to elaborate?"
        await sm.remove_followup_message(sid, queue[0]["id"])
        queue = await sm.get_followup_queue(sid)
        assert len(queue) == 0
    finally:
        await sm.close()


@pytest.mark.asyncio
async def test_steering_inject_prepends_system_message():
    """node_steering_inject should prepend steering messages as SystemMessage."""
    from openchain.agent.nodes import node_steering_inject
    from openchain.agent.state import AgentState
    from langchain_core.messages import SystemMessage

    state = AgentState(
        session_id="test",
        workspace="/tmp",
        input_message="hello",
        parent_node_id=None,
        model="claude-sonnet-4-7",
        messages=[],
        tool_calls=[],
        tool_results=[],
        current_tool_call_index=0,
        error=None,
        retry_count=0,
        security_context={},
        steering_queue=[{"id": "1", "content": "Be concise."}],
    )
    new_state = await node_steering_inject(state)
    assert len(new_state["messages"]) == 1
    assert "Be concise" in new_state["messages"][0].content


@pytest.mark.asyncio
async def test_followup_cleared_after_response():
    """node_finalize_followup should clear followup queue."""
    from openchain.agent.nodes import node_finalize_followup
    from openchain.agent.state import AgentState

    state = AgentState(
        session_id="test",
        workspace="/tmp",
        input_message="hello",
        parent_node_id=None,
        model="claude-sonnet-4-7",
        messages=[],
        tool_calls=[],
        tool_results=[],
        current_tool_call_index=0,
        error=None,
        retry_count=0,
        security_context={},
        steering_queue=[],
        followup_queue=[{"id": "1", "content": "Want me to elaborate?"}],
    )
    new_state = await node_finalize_followup(state)
    assert len(new_state["followup_queue"]) == 0