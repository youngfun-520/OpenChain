"""Tests for session management."""
import pytest
from openchain.session import SessionManager, NodeNotFoundError


@pytest.mark.asyncio
async def test_create_session():
    sm = SessionManager(":memory:")
    await sm.initialize()
    session = await sm.create_session(workspace="/tmp")
    assert session["session_id"] is not None
    assert session["workspace"] == "/tmp"


@pytest.mark.asyncio
async def test_save_and_load_node():
    sm = SessionManager(":memory:")
    await sm.initialize()
    session = await sm.create_session(workspace="/tmp")
    node = await sm.save_user_message_node(
        session_id=session["session_id"],
        content="Hello"
    )
    assert node["node_id"] is not None
    assert node["role"] == "user"
    loaded = await sm.load_node(node["node_id"])
    assert loaded["content"] == "Hello"


@pytest.mark.asyncio
async def test_get_ancestor_chain():
    sm = SessionManager(":memory:")
    await sm.initialize()
    session = await sm.create_session(workspace="/tmp")
    n1 = await sm.save_user_message_node(session["session_id"], "msg1")
    n2 = await sm.save_assistant_message_node(session["session_id"], n1["node_id"], "resp1")
    n3 = await sm.save_user_message_node(session["session_id"], "msg2", n2["node_id"])
    chain = await sm.get_ancestor_chain(n3["node_id"])
    assert len(chain) == 3
    node_ids = [n["node_id"] for n in chain]
    assert n1["node_id"] in node_ids
    assert n2["node_id"] in node_ids
    assert n3["node_id"] in node_ids


@pytest.mark.asyncio
async def test_fork_session():
    sm = SessionManager(":memory:")
    await sm.initialize()
    session = await sm.create_session(workspace="/tmp")
    n1 = await sm.save_user_message_node(session["session_id"], "msg1")
    n2 = await sm.save_assistant_message_node(session["session_id"], n1["node_id"], "resp1")
    forked = await sm.fork_session(session["session_id"], n2["node_id"])
    assert forked["session_id"] != session["session_id"]
    nodes = await sm.get_session_nodes(forked["session_id"])
    assert len(nodes) == 2  # n1 and n2 (ancestor chain)