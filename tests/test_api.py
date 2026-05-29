"""Tests for API."""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from openchain.api.routes import app

@pytest.fixture(autouse=True)
def setup_api_key():
    """Ensure OPENCHAIN_API_KEYS is set for each test."""
    os.environ["OPENCHAIN_API_KEYS"] = "test-key-123"
    yield
    os.environ.pop("OPENCHAIN_API_KEYS", None)

API_KEY_HEADER = {"X-API-Key": "test-key-123"}


@pytest.mark.asyncio
async def test_api_health():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_api_create_session():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post("/sessions", json={"workspace": "/tmp"}, headers=API_KEY_HEADER)
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data


@pytest.mark.asyncio
async def test_api_chat():
    mock_result = {
        "messages": [MagicMock(content="Hello, how can I help you?")],
        "tool_calls": [],
        "tool_results": [],
    }
    with patch("openchain.api.routes.build_graph") as mock_build_graph:
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value=mock_result)
        mock_build_graph.return_value = mock_graph

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            sess_resp = await client.post("/sessions", json={"workspace": "/tmp"}, headers=API_KEY_HEADER)
            session_id = sess_resp.json()["session_id"]
            response = await client.post("/chat", json={
                "message": "Hello",
                "session_id": session_id
            }, headers=API_KEY_HEADER)
            assert response.status_code == 200
            data = response.json()
            assert "response" in data or "node_id" in data