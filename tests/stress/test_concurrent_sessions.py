"""Stress tests for concurrent session access."""
import pytest
import asyncio
import os


@pytest.mark.asyncio
async def test_concurrent_session_creation():
    """Multiple concurrent session creates should not conflict."""
    from openchain.session import SessionManager
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "concurrent.db")

        async def create_session(i):
            async with SessionManager(db_path) as sm:
                await sm.initialize()
                session = await sm.create_session(workspace=f"/tmp/ws{i}")
                return session["session_id"]

        # Run 10 concurrent session creates
        tasks = [create_session(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert len(set(results)) == 10  # All unique session IDs


@pytest.mark.asyncio
async def test_concurrent_message_save():
    """Multiple concurrent message saves to same session should not conflict."""
    from openchain.session import SessionManager
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "concurrent.db")

        async with SessionManager(db_path) as sm:
            await sm.initialize()
            session = await sm.create_session(workspace="/tmp/ws")

            async def save_message(i):
                await sm.save_user_message_node(
                    session["session_id"], f"Message {i}", parent_node_id=None
                )
                return i

            tasks = [save_message(i) for i in range(10)]
            results = await asyncio.gather(*tasks)

            assert len(results) == 10

            # Verify all messages were saved
            nodes = await sm.get_session_nodes(session["session_id"])
            assert len(nodes) == 10


@pytest.mark.asyncio
async def test_concurrent_tool_call_logging():
    """Tool calls should be logged correctly under concurrent access."""
    from openchain.db import Database
    import tempfile
    import uuid

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "audit_concurrent.db")

        async def log_tool_call(i):
            async with Database(db_path) as db:
                call_id = str(uuid.uuid4())
                await db.execute(
                    """INSERT INTO tool_calls
                       (call_id, node_id, session_id, tool_name, arguments, result, status,
                        security_verified, user_confirmed)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (call_id, f"node-{i}", f"session-{i}", "read_file",
                     "{}", "{}", "success", 0, 0)
                )
                await db.commit()
                return call_id

        tasks = [log_tool_call(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10

        # Verify all records were inserted
        async with Database(db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM tool_calls") as cursor:
                row = await cursor.fetchone()
                count = row[0] if row else 0
            assert count == 10, f"Expected 10 records, got {count}"


@pytest.mark.asyncio
async def test_concurrent_audit_logging():
    """Audit logs should be written correctly under concurrent load."""
    from openchain.db import Database
    import tempfile
    import uuid

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "audit_concurrent.db")

        async def log_audit(i):
            async with Database(db_path) as db:
                log_id = str(uuid.uuid4())
                await db.execute(
                    """INSERT INTO audit_logs
                       (log_id, key_label, endpoint, method, status_code, client_ip, request_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (log_id, f"key-{i}", f"/endpoint-{i}", "GET", 200, "127.0.0.1", f"req-{i}")
                )
                await db.commit()
                return log_id

        tasks = [log_audit(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10

        async with Database(db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM audit_logs") as cursor:
                row = await cursor.fetchone()
                count = row[0] if row else 0
            assert count == 10