"""Session management with message node tree."""
import uuid
import json
from typing import Optional
from openchain.db import Database


class NodeNotFoundError(Exception):
    """Node not found in database."""
    pass


class SessionManager:
    def __init__(self, db_path: str = "~/.openchain/data/openchain.db"):
        self.db = Database(db_path)

    async def __aenter__(self) -> "SessionManager":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit — always closes connection."""
        await self.close()

    async def initialize(self):
        await self.db.initialize()

    async def close(self):
        if self.db:
            await self.db.close()
            self.db = None

    async def list_sessions(self) -> list[dict]:
        """List all sessions ordered by creation time."""
        cursor = await self.db.execute("SELECT * FROM sessions ORDER BY created_at DESC")
        async with cursor:
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]

    async def create_session(
        self,
        workspace: str,
        model: Optional[str] = None,
        parent_node_id: Optional[str] = None
    ) -> dict:
        """Create a new session."""
        session_id = str(uuid.uuid4())
        await self.db.execute(
            "INSERT INTO sessions (session_id, workspace, model) VALUES (?, ?, ?)",
            (session_id, workspace, model)
        )
        await self.db.commit()
        return {
            "session_id": session_id,
            "workspace": workspace,
            "model": model,
            "created_at": None
        }

    async def save_user_message_node(
        self,
        session_id: str,
        content: str,
        parent_node_id: Optional[str] = None
    ) -> dict:
        """Save a user message node."""
        return await self._save_message_node(
            session_id=session_id,
            role="user",
            content=content,
            parent_node_id=parent_node_id
        )

    async def save_assistant_message_node(
        self,
        session_id: str,
        parent_node_id: str,
        content: str,
        tool_calls: Optional[list] = None,
        tool_results: Optional[list] = None,
        model: Optional[str] = None
    ) -> dict:
        """Save an assistant message node."""
        return await self._save_message_node(
            session_id=session_id,
            role="assistant",
            content=content,
            parent_node_id=parent_node_id,
            tool_calls=tool_calls,
            tool_results=tool_results,
            model=model
        )

    async def _save_message_node(
        self,
        session_id: str,
        role: str,
        content: str,
        parent_node_id: Optional[str] = None,
        tool_calls: Optional[list] = None,
        tool_results: Optional[list] = None,
        model: Optional[str] = None
    ) -> dict:
        """Internal method to save a message node."""
        node_id = str(uuid.uuid4())
        await self.db.execute(
            """INSERT INTO message_nodes
               (node_id, session_id, parent_node_id, role, content, tool_calls, tool_results, model)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (node_id, session_id, parent_node_id, role, content,
             json.dumps(tool_calls) if tool_calls else None,
             json.dumps(tool_results) if tool_results else None,
             model)
        )
        await self.db.commit()
        return {
            "node_id": node_id,
            "session_id": session_id,
            "parent_node_id": parent_node_id,
            "role": role,
            "content": content,
            "tool_calls": tool_calls,
            "tool_results": tool_results
        }

    async def load_node(self, node_id: str) -> dict:
        """Load a single node by ID."""
        cursor = await self.db.execute(
            "SELECT * FROM message_nodes WHERE node_id = ?", (node_id,)
        )
        async with cursor:
            row = await cursor.fetchone()
            if not row:
                raise NodeNotFoundError(f"Node {node_id} not found")
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))

    async def get_session_nodes(self, session_id: str) -> list[dict]:
        """Get all nodes for a session in order."""
        cursor = await self.db.execute(
            "SELECT * FROM message_nodes WHERE session_id = ? ORDER BY created_at",
            (session_id,)
        )
        async with cursor:
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]

    async def get_ancestor_chain(self, node_id: str) -> list[dict]:
        """Get ancestor chain from root to node (inclusive)."""
        chain = []
        current_id = node_id
        visited = set()
        while current_id and current_id not in visited:
            visited.add(current_id)
            node = await self.load_node(current_id)
            chain.append(node)
            current_id = node.get("parent_node_id")
        return list(reversed(chain))

    async def fork_session(self, session_id: str, node_id: str) -> dict:
        """Fork a session from a specific node.

        Creates a new session and copies the ancestor chain of node_id.
        """
        ancestor_chain = await self.get_ancestor_chain(node_id)
        new_session = await self.create_session(workspace="")
        # Load original session to get workspace
        cursor = await self.db.execute(
            "SELECT workspace FROM sessions WHERE session_id = ?", (session_id,)
        )
        async with cursor:
            row = await cursor.fetchone()
            if row:
                await self.db.execute(
                    "UPDATE sessions SET workspace = ? WHERE session_id = ?",
                    (row[0], new_session["session_id"])
                )
                await self.db.commit()
        # Copy ancestor chain to new session with new node_ids
        old_to_new_id = {}
        for old_node in ancestor_chain:
            new_parent = old_to_new_id.get(old_node["parent_node_id"])
            new_node = await self._save_message_node(
                session_id=new_session["session_id"],
                role=old_node["role"],
                content=old_node["content"],
                parent_node_id=new_parent,
                tool_calls=json.loads(old_node["tool_calls"]) if old_node["tool_calls"] else None,
                tool_results=json.loads(old_node["tool_results"]) if old_node["tool_results"] else None,
                model=old_node["model"]
            )
            old_to_new_id[old_node["node_id"]] = new_node["node_id"]
        return {
            **new_session,
            "forked_from_node_id": node_id,
            "parent_node_id": old_to_new_id[node_id]
        }

    async def get_session_tree(self, session_id: str) -> list[dict]:
        """Get session tree structure (nodes with parent info)."""
        return await self.get_session_nodes(session_id)