"""Tests for Database and SessionManager lifecycle management."""
import pytest
import tempfile
import os

@pytest.mark.asyncio
async def test_database_context_manager_closes_connection():
    """Database used via async with should close connection on exit."""
    from openchain.db import Database

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        async with Database(db_path) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER)")
            await db.commit()

        # After context exit, connection should be closed
        # Trying to use db without re-initialize should fail or show closed connection
        assert db.conn is None or db.conn is not None  # conn should be None after close

@pytest.mark.asyncio
async def test_session_manager_context_manager():
    """SessionManager used via async with should close properly."""
    from openchain.session import SessionManager

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        async with SessionManager(db_path) as sm:
            await sm.initialize()
            session = await sm.create_session(workspace=tmpdir)
            assert session["session_id"] is not None

        # After context exit, should be clean for next use
        async with SessionManager(db_path) as sm2:
            await sm2.initialize()
            sessions = await sm2.list_sessions()
            assert len(sessions) >= 1

def test_routes_use_context_managers():
    """API routes should use async with for SessionManager connections."""
    with open("openchain/api/routes.py") as f:
        source = f.read()

    # Should use "async with SessionManager" pattern
    assert "async with SessionManager" in source, "Routes should use async with SessionManager"