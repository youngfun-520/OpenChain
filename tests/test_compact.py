"""Tests for history compression (compact) functionality."""
import pytest
import tempfile
import os
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_compact_summary_column_exists():
    """message_nodes table should have compact_summary TEXT column."""
    from openchain.db import Database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        async with Database(db_path) as db:
            await db.initialize()
            cursor = await db.conn.execute("PRAGMA table_info(message_nodes)")
            columns = {row[1] for row in await cursor.fetchall()}
            assert "compact_summary" in columns, f"compact_summary missing: {columns}"


@pytest.mark.asyncio
async def test_compact_session_reduces_messages():
    """compact_session should mark old user messages with compact_summary, not delete them."""
    from openchain.session import SessionManager
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        sm = SessionManager(db_path=db_path)
        await sm.initialize()
        try:
            session = await sm.create_session(workspace="/tmp")
            sid = session["session_id"]
            parent = None
            # Create 5 user messages
            for i in range(5):
                node = await sm.save_user_message_node(sid, f"Message {i}", parent)
                parent = node["node_id"]
            # Compact
            with patch("langchain_anthropic.ChatAnthropic") as mock_chat:
                mock_llm = AsyncMock()
                mock_result = AsyncMock()
                mock_result.content = "Summarized history."
                mock_llm.ainvoke = AsyncMock(return_value=mock_result)
                mock_chat.return_value = mock_llm

                result = await sm.compact_session(sid)
            assert result["status"] == "success"
            # Verify messages still exist, but are marked with compact_summary
            nodes = await sm.get_session_nodes(sid)
            # All 5 messages should still exist (NOT deleted)
            assert len(nodes) == 5
            # At least some should have compact_summary set
            summarized = [n for n in nodes if n.get("compact_summary")]
            assert len(summarized) >= 2
        finally:
            await sm.close()


def test_cli_compact_command():
    """CLI should have /compact command registered."""
    from openchain.cli import REPL_COMMANDS
    assert "/compact" in REPL_COMMANDS, f"/compact not in {list(REPL_COMMANDS.keys())}"