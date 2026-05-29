"""Tests for database layer."""
import pytest
import aiosqlite
from openchain.db import Database, SCHEMA_SQL


@pytest.mark.asyncio
async def test_database_init():
    db = Database(":memory:")
    await db.initialize()
    assert db.conn is not None


@pytest.mark.asyncio
async def test_database_tables_exist():
    db = Database(":memory:")
    await db.initialize()
    async with db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ) as cursor:
        tables = await cursor.fetchall()
        table_names = [r[0] for r in tables]
        assert "sessions" in table_names
        assert "message_nodes" in table_names
        assert "tool_calls" in table_names