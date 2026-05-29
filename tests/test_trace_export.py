"""Tests for trace export functionality."""
import os
import pytest
from httpx import AsyncClient, ASGITransport
from openchain.api.routes import app


@pytest.mark.asyncio
async def test_export_trace_method_exists():
    """SessionManager should have an export_trace method."""
    from openchain.session import SessionManager

    sm = SessionManager(":memory:")
    await sm.initialize()
    try:
        session = await sm.create_session(workspace="/tmp")
        sid = session["session_id"]
        assert hasattr(sm, "export_trace"), "export_trace method not found"
    finally:
        await sm.close()


@pytest.mark.asyncio
async def test_export_trace_contains_full_session():
    """export_trace should return all nodes, tool_calls, and audit_logs."""
    from openchain.session import SessionManager

    sm = SessionManager(":memory:")
    await sm.initialize()
    try:
        session = await sm.create_session(workspace="/tmp")
        sid = session["session_id"]
        node = await sm.save_user_message_node(sid, "Hello", None)
        await sm.save_assistant_message_node(sid, node["node_id"], "Hi", model="test")
        trace = await sm.export_trace(sid)
        assert "session_id" in trace
        assert "nodes" in trace
        assert "metadata" in trace
        assert "tool_calls" in trace
        assert "audit_logs" in trace
        assert len(trace["nodes"]) == 2
    finally:
        await sm.close()


@pytest.mark.asyncio
async def test_api_trace_endpoint():
    """GET /sessions/{id}/trace should return JSON trace."""
    os.environ["OPENCHAIN_API_KEYS"] = "test-key:read,write,admin"
    API_KEY_HEADER = {"X-API-Key": "test-key"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/sessions", json={"workspace": "/tmp"}, headers=API_KEY_HEADER)
        sid = create_resp.json()["session_id"]
        trace_resp = await client.get(f"/sessions/{sid}/trace", headers=API_KEY_HEADER)
        assert trace_resp.status_code == 200
        data = trace_resp.json()
        assert "session_id" in data
        assert "nodes" in data


@pytest.mark.asyncio
async def test_write_trace_to_file(tmp_path):
    """write_trace_to_file should write serialized trace to a .json file."""
    import json
    from openchain.session import SessionManager
    from openchain.tools.trace_export import write_trace_to_file

    sm = SessionManager(":memory:")
    await sm.initialize()
    try:
        session = await sm.create_session(workspace="/tmp")
        sid = session["session_id"]
        output_path = tmp_path / "trace.json"
        result = await write_trace_to_file(sm, sid, str(output_path))
        assert result["status"] == "success"
        assert output_path.exists()
        with open(output_path) as f:
            data = json.load(f)
        assert "session_id" in data
    finally:
        await sm.close()