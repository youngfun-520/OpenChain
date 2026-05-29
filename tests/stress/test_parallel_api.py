"""Parallel API tests using pytest-xdist."""
import pytest
import os
from concurrent.futures import ThreadPoolExecutor


def test_parallel_session_list():
    """GET /sessions should work under parallel load."""
    from fastapi.testclient import TestClient
    from openchain.api.routes import app

    os.environ["OPENCHAIN_API_KEYS"] = "test-key"

    client = TestClient(app, raise_server_exceptions=False)

    def fetch_sessions():
        return client.get("/sessions", headers={"X-API-Key": "test-key"})

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_sessions) for _ in range(10)]
        responses = [f.result() for f in futures]

    # All should return non-401
    for r in responses:
        assert r.status_code != 401, f"Expected non-401, got {r.status_code}"

    os.environ.pop("OPENCHAIN_API_KEYS", None)


def test_parallel_session_create():
    """POST /sessions should work under parallel load."""
    from fastapi.testclient import TestClient
    from openchain.api.routes import app

    os.environ["OPENCHAIN_API_KEYS"] = "test-key"

    client = TestClient(app, raise_server_exceptions=False)

    def create_session(i):
        return client.post("/sessions", json={"workspace": f"/tmp/ws{i}"}, headers={"X-API-Key": "test-key"})

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(create_session, i) for i in range(10)]
        responses = [f.result() for f in futures]

    # All should return non-401
    for r in responses:
        assert r.status_code != 401

    os.environ.pop("OPENCHAIN_API_KEYS", None)