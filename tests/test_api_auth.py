"""Tests for API key authentication."""
import pytest
import os

def test_protected_routes_require_api_key():
    """All routes except /health should require X-API-Key header."""
    from fastapi.testclient import TestClient
    from openchain.api.routes import app

    os.environ["OPENCHAIN_API_KEYS"] = "test-key-123"

    client = TestClient(app, raise_server_exceptions=False)

    # Without API key - should get 401
    response = client.get("/sessions")
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    response = client.post("/sessions")
    assert response.status_code == 401

    response = client.post("/chat", json={"message": "hello", "session_id": "test"})
    assert response.status_code == 401

    # Health should still be accessible without API key
    response = client.get("/health")
    assert response.status_code == 200

    os.environ.pop("OPENCHAIN_API_KEYS", None)

def test_valid_api_key_accepted():
    """Requests with valid API key should succeed."""
    from fastapi.testclient import TestClient
    from openchain.api.routes import app

    os.environ["OPENCHAIN_API_KEYS"] = "test-key-123"

    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/sessions", headers={"X-API-Key": "test-key-123"})
    # Should not be 401 - could be 200 or 500 (if DB issues), but not 401
    assert response.status_code != 401, f"Expected non-401, got {response.status_code}"

    os.environ.pop("OPENCHAIN_API_KEYS", None)

def test_invalid_api_key_rejected():
    """Requests with invalid API key should get 401."""
    from fastapi.testclient import TestClient
    from openchain.api.routes import app

    os.environ["OPENCHAIN_API_KEYS"] = "valid-key"

    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/sessions", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    os.environ.pop("OPENCHAIN_API_KEYS", None)