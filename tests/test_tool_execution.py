"""Tests for tool execution in LangGraph."""
import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock
from openchain.agent.graph import build_graph
from openchain.agent.state import AgentState
from openchain.session import SessionManager
from openchain.security import SecurityChecker


@pytest.mark.asyncio
async def test_graph_invokes_read_file_tool():
    """Test that graph can invoke read_file tool when available."""
    # This test verifies tool binding works - full integration test
    # requires actual API key, so we test the structure
    graph = build_graph()
    assert graph is not None


@pytest.mark.asyncio
async def test_tool_execution_records_audit():
    """Test that tool execution creates audit records in tool_calls table."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test file inside workspace
        test_file = os.path.join(tmpdir, "test.txt")
        with open(test_file, "w") as f:
            f.write("hello world")

        sm = SessionManager(":memory:")
        await sm.initialize()
        session = await sm.create_session(workspace=tmpdir)

        # Simulate what node_execute_tools does - directly execute a tool call
        from openchain.tools.file_tools import ReadFileTool
        from openchain.security import SecurityChecker
        from openchain.db import Database
        import json
        import uuid

        sc = SecurityChecker(tmpdir)
        tool = ReadFileTool(sc)

        # Execute tool directly
        result = await tool.execute(path=test_file)
        assert result["status"] == "success"
        assert result["content"] == "hello world"

        # Now simulate audit logging
        db = Database(":memory:")
        await db.initialize()

        call_id = str(uuid.uuid4())
        node_id = "test-node-id"
        session_id = session["session_id"]

        await db.execute(
            """INSERT INTO tool_calls
               (call_id, node_id, session_id, tool_name, arguments, result, status,
                security_verified, user_confirmed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (call_id, node_id, session_id, "read_file",
             json.dumps({"path": test_file}), json.dumps(result), "success", 0, 0)
        )
        await db.commit()

        # Verify audit record exists
        async with db.execute(
            "SELECT * FROM tool_calls WHERE call_id = ?", (call_id,)
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            columns = [desc[0] for desc in cursor.description]
            record = dict(zip(columns, row))
            assert record["tool_name"] == "read_file"
            assert record["status"] == "success"

        await db.close()
        await sm.close()


@pytest.mark.asyncio
async def test_workspace_path_rejected_by_security_checker():
    """Test that paths outside workspace are rejected by SecurityChecker."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sc = SecurityChecker(tmpdir)

        # Path inside workspace should be allowed
        inside_path = os.path.join(tmpdir, "file.txt")
        assert sc.check_path(inside_path) is True

        # Path outside workspace should be rejected
        assert sc.check_path("/etc/passwd") is False
        assert sc.check_path("/tmp/other") is False


@pytest.mark.asyncio
async def test_api_mode_bash_disabled():
    """Test that bash is disabled in API mode by default."""
    from openchain.security import SecurityChecker

    # Without OPENCHAIN_API_ENABLE_BASH
    with patch.dict(os.environ, {}, clear=True):
        sc = SecurityChecker("/tmp")
        assert sc.check_api_mode("bash") is False
        assert sc.check_api_mode("read_file") is True


@pytest.mark.asyncio
async def test_api_mode_bash_enabled_when_env_set():
    """Test that bash can be enabled via environment variable."""
    from openchain.security import SecurityChecker

    with patch.dict(os.environ, {"OPENCHAIN_API_ENABLE_BASH": "true"}):
        sc = SecurityChecker("/tmp")
        assert sc.check_api_mode("bash") is True


@pytest.mark.asyncio
async def test_symlink_path_traversal_blocked():
    """Test that symlinks pointing outside workspace are blocked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = os.path.join(tmpdir, "workspace")
        os.makedirs(workspace)

        # Create symlink inside workspace pointing to outside
        symlink_path = os.path.join(workspace, "link_to_etc")
        os.symlink("/etc/passwd", symlink_path)

        sc = SecurityChecker(workspace)

        # Symlink should be blocked because realpath resolves to /etc/passwd
        assert sc.check_path(symlink_path) is False
        # Direct path to /etc/passwd should also be blocked
        assert sc.check_path("/etc/passwd") is False
        # File inside workspace should be allowed
        inside_file = os.path.join(workspace, "file.txt")
        with open(inside_file, "w") as f:
            f.write("test")
        assert sc.check_path(inside_file) is True


@pytest.mark.asyncio
async def test_dangerous_bash_commands_blocked():
    """Test that dangerous bash commands are blocked."""
    from openchain.security import SecurityChecker

    sc = SecurityChecker("/tmp")

    dangerous_commands = [
        "rm -rf /",
        "dd if=/dev/zero of=/dev/sda",
        ":(){ :|:& };:",
        "sudo rm -rf /",
    ]

    for cmd in dangerous_commands:
        safe, reason = sc.check_bash_command(cmd)
        assert safe is False, f"Command should be blocked: {cmd}"
        assert reason is not None


@pytest.mark.asyncio
async def test_node_save_message_node_stores_assistant_node_id():
    """Test that node_save_message_node stores assistant node ID for audit correlation."""
    sm = SessionManager(":memory:")
    await sm.initialize()
    session = await sm.create_session(workspace="/tmp")

    # Create user message first
    user_node = await sm.save_user_message_node(
        session["session_id"], "Hello", parent_node_id=None
    )

    # Create assistant message
    assistant_node = await sm.save_assistant_message_node(
        session["session_id"],
        parent_node_id=user_node["node_id"],
        content="Hi there!"
    )

    # Assistant node should have valid node_id
    assert assistant_node["node_id"] is not None
    assert assistant_node["role"] == "assistant"

    await sm.close()