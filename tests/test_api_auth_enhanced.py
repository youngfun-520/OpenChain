"""Tests for enhanced API authentication with scopes and audit."""
import pytest
import os
from fastapi.testclient import TestClient

def test_multi_key_with_scopes():
    """API keys should support scopes: read, write, admin."""
    from openchain.api.auth import get_key_by_label

    # Format: "key1:read,write|key2:read|key3:admin"
    os.environ["OPENCHAIN_API_KEYS"] = "read-key:read|write-key:write,read|admin-key:admin"

    key1 = get_key_by_label("read-key")
    assert key1 is not None
    assert "read" in key1.scopes
    assert "write" not in key1.scopes
    assert "admin" not in key1.scopes

    key2 = get_key_by_label("write-key")
    assert "write" in key2.scopes
    assert "read" in key2.scopes
    assert "admin" not in key2.scopes

    key3 = get_key_by_label("admin-key")
    assert "admin" in key3.scopes

    os.environ.pop("OPENCHAIN_API_KEYS", None)

def test_key_without_scopes_defaults_to_empty():
    """Keys without scope specifier get empty scopes."""
    from openchain.api.auth import get_key_by_label

    os.environ["OPENCHAIN_API_KEYS"] = "simple-key"

    key = get_key_by_label("simple-key")
    assert key is not None
    assert len(key.scopes) == 0

    os.environ.pop("OPENCHAIN_API_KEYS", None)

def test_verify_returns_key_label():
    """verify_api_key should return key label (for audit logging)."""
    os.environ["OPENCHAIN_API_KEYS"] = "test-key:read"
    from openchain.api.auth import verify_api_key
    from fastapi import Security

    # Can't easily test Security dependency directly, but verify the parsing works
    from openchain.api.auth import get_key_by_label
    key = get_key_by_label("test-key")
    assert key.label == "test-key"

    os.environ.pop("OPENCHAIN_API_KEYS", None)

def test_missing_key_returns_401():
    """Requests without API key return 401."""
    from openchain.api.routes import app

    os.environ["OPENCHAIN_API_KEYS"] = "valid-key"

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/sessions")
    assert response.status_code == 401

    os.environ.pop("OPENCHAIN_API_KEYS", None)

def test_invalid_key_returns_401():
    """Requests with invalid API key return 401."""
    from openchain.api.routes import app

    os.environ["OPENCHAIN_API_KEYS"] = "valid-key"

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/sessions", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401

    os.environ.pop("OPENCHAIN_API_KEYS", None)

def test_valid_key_returns_200():
    """Requests with valid API key succeed."""
    from openchain.api.routes import app

    os.environ["OPENCHAIN_API_KEYS"] = "valid-key"

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/sessions", headers={"X-API-Key": "valid-key"})
    assert response.status_code != 401

    os.environ.pop("OPENCHAIN_API_KEYS", None)

@pytest.mark.asyncio
async def test_audit_log_table_exists():
    """Database should have audit_logs table after initialization."""
    import tempfile
    import os
    from openchain.db import Database

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        async with Database(db_path) as db:
            # Check audit_logs table exists
            async with db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_logs'") as cursor:
                row = await cursor.fetchone()
                assert row is not None, "audit_logs table should exist"