"""SQLite database layer."""
import aiosqlite
from pathlib import Path
from typing import Optional
import json

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    workspace TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS message_nodes (
    node_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    parent_node_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_calls TEXT,
    tool_results TEXT,
    model TEXT,
    token_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (parent_node_id) REFERENCES message_nodes(node_id)
);

CREATE TABLE IF NOT EXISTS tool_calls (
    call_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    arguments TEXT NOT NULL,
    result TEXT,
    status TEXT NOT NULL,
    security_verified BOOLEAN DEFAULT FALSE,
    user_confirmed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (node_id) REFERENCES message_nodes(node_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_nodes_session ON message_nodes(session_id);
CREATE INDEX IF NOT EXISTS idx_nodes_parent ON message_nodes(parent_node_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls(session_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_node ON tool_calls(node_id);

CREATE TABLE IF NOT EXISTS audit_logs (
    log_id TEXT PRIMARY KEY,
    key_label TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    status_code INTEGER,
    client_ip TEXT,
    request_id TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    def __init__(self, db_path: str = "~/.openchain/data/openchain.db"):
        self.db_path = Path(db_path).expanduser()
        self.conn: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(str(self.db_path))
        await self.conn.executescript(SCHEMA_SQL)
        await self.conn.commit()

    async def __aenter__(self) -> "Database":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit — always closes connection."""
        await self.close()

    async def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            try:
                await self.conn.close()
            except Exception:
                pass
            self.conn = None

    def execute(self, sql: str, params: tuple = ()):
        return self.conn.execute(sql, params)

    def executemany(self, sql: str, params: list):
        return self.conn.executemany(sql, params)

    async def commit(self):
        await self.conn.commit()