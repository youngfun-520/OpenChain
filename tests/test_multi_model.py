"""Tests for multi-model switching features."""
import pytest
from openchain.model_registry import ModelRegistry


def test_resolve_model_with_override():
    """resolve_model should prefer session override if valid."""
    mr = ModelRegistry()
    # If no override, returns requested
    result = mr.resolve_model("claude-sonnet-4-7")
    assert result is not None
    # If override is valid, returns override
    result = mr.resolve_model("claude-sonnet-4-7", session_override="claude-haiku-4-5")
    assert result == "claude-haiku-4-5"


def test_validate_model_config_raises_on_invalid():
    """validate_model_config should raise ModelNotFoundError for unknown models."""
    mr = ModelRegistry()
    # Should not raise for known models
    mr.validate_model_config("claude-sonnet-4-7")
    # Should raise for unknown models
    try:
        mr.validate_model_config("unknown-model-xyz")
        assert False, "Should have raised ModelNotFoundError"
    except Exception as e:
        assert "not available" in str(e)


@pytest.mark.asyncio
async def test_create_session_with_model():
    """create_session should accept and persist model parameter."""
    from openchain.session import SessionManager
    sm = SessionManager()
    await sm.initialize()
    try:
        session = await sm.create_session(workspace="/tmp", model="claude-haiku-4-5")
        assert session["model"] == "claude-haiku-4-5"
        loaded = await sm.get_session(session["session_id"])
        assert loaded["model"] == "claude-haiku-4-5"
    finally:
        await sm.close()


@pytest.mark.asyncio
async def test_update_session_model():
    """update_session_model should update the model's session."""
    from openchain.session import SessionManager
    sm = SessionManager()
    await sm.initialize()
    try:
        session = await sm.create_session(workspace="/tmp")
        sid = session["session_id"]
        await sm.update_session_model(sid, "claude-opus-4-7")
        loaded = await sm.get_session(sid)
        assert loaded["model"] == "claude-opus-4-7"
    finally:
        await sm.close()


@pytest.mark.asyncio
async def test_api_update_session_model():
    """PATCH /sessions/{id} should update session model."""
    import os
    os.environ["OPENCHAIN_API_KEYS"] = "test-key:read,write,admin"
    from httpx import AsyncClient, ASGITransport
    from openchain.api.routes import app

    API_KEY_HEADER = {"X-API-Key": "test-key"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/sessions", json={"workspace": "/tmp"}, headers=API_KEY_HEADER)
        sid = create_resp.json()["session_id"]
        patch_resp = await client.patch(f"/sessions/{sid}", json={"model": "claude-haiku-4-5"}, headers=API_KEY_HEADER)
        assert patch_resp.status_code == 200
        assert patch_resp.json()["model"] == "claude-haiku-4-5"