"""Session management with message node tree."""
import uuid
import json
from typing import Optional, Any
from langchain_core.messages import HumanMessage
from openchain.db import Database
from openchain.model_registry import ModelRegistry


class NodeNotFoundError(Exception):
    """Node not found in database."""
    pass


class SessionManager:
    # Default queue_messages structure
    _DEFAULT_QUEUE_MESSAGES = {"steering": [], "followup": []}

    def __init__(self, db_path: str = "~/.openchain/data/openchain.db"):
        self.db = Database(db_path)

    @staticmethod
    def _parse_queue_messages(value: Optional[str]) -> dict:
        """Parse queue_messages JSON column with default structure."""
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        return SessionManager._DEFAULT_QUEUE_MESSAGES.copy()

    @staticmethod
    def _parse_json_field(value: Optional[str], default: Any = None) -> Any:
        """Parse a JSON field, returning default if null or decode fails."""
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        return default

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
        # Read back to get actual created_at timestamp from DB
        cursor = await self.db.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        )
        async with cursor:
            row = await cursor.fetchone()
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))

    async def update_session_model(self, session_id: str, model: str) -> None:
        """Update the model for an existing session."""
        mr = ModelRegistry()
        mr.validate_model_config(model)
        await self.db.execute(
            "UPDATE sessions SET model = ?, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
            (model, session_id)
        )
        await self.db.commit()

    async def touch_session(self, session_id: str) -> None:
        """Update the updated_at timestamp for a session."""
        await self.db.execute(
            "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
            (session_id,)
        )
        await self.db.commit()

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
        # Load original session to get workspace and model
        cursor = await self.db.execute(
            "SELECT workspace, model FROM sessions WHERE session_id = ?", (session_id,)
        )
        async with cursor:
            row = await cursor.fetchone()
            if not row:
                raise ValueError(f"Session {session_id} not found")
            workspace, model = row[0], row[1]
        new_session = await self.create_session(workspace=workspace, model=model)
        # Copy ancestor chain to new session with new node_ids
        old_to_new_id = {}
        for old_node in ancestor_chain:
            new_parent = old_to_new_id.get(old_node["parent_node_id"])
            new_node = await self._save_message_node(
                session_id=new_session["session_id"],
                role=old_node["role"],
                content=old_node["content"],
                parent_node_id=new_parent,
                tool_calls=SessionManager._parse_json_field(old_node["tool_calls"]),
                tool_results=SessionManager._parse_json_field(old_node["tool_results"]),
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

    async def add_steering_message(self, session_id: str, content: str, position: int = -1) -> dict:
        """Add a steering message to the session's queue."""
        cursor = await self.db.execute(
            "SELECT queue_messages FROM sessions WHERE session_id = ?", (session_id,)
        )
        async with cursor:
            row = await cursor.fetchone()
        if not row:
            return {"status": "error", "message": "session not found"}
        queue_data = self._parse_queue_messages(row[0])
        msg = {"id": str(uuid.uuid4()), "content": content}
        if position < 0:
            queue_data["steering"].append(msg)
        else:
            queue_data["steering"].insert(position, msg)
        await self.db.execute(
            "UPDATE sessions SET queue_messages = ? WHERE session_id = ?",
            (json.dumps(queue_data), session_id)
        )
        await self.db.commit()
        return {"status": "success", "message": msg}

    async def get_steering_queue(self, session_id: str) -> list:
        """Get all steering messages for a session."""
        cursor = await self.db.execute(
            "SELECT queue_messages FROM sessions WHERE session_id = ?", (session_id,)
        )
        async with cursor:
            row = await cursor.fetchone()
        if not row:
            return []
        queue_data = json.loads(row[0] or '{"steering": []}')
        return queue_data["steering"]

    async def remove_steering_message(self, session_id: str, message_id: str) -> dict:
        """Remove a steering message by id."""
        cursor = await self.db.execute(
            "SELECT queue_messages FROM sessions WHERE session_id = ?", (session_id,)
        )
        async with cursor:
            row = await cursor.fetchone()
        if not row:
            return {"status": "error", "message": "session not found"}
        queue_data = self._parse_queue_messages(row[0])
        queue_data["steering"] = [m for m in queue_data["steering"] if m["id"] != message_id]
        await self.db.execute(
            "UPDATE sessions SET queue_messages = ? WHERE session_id = ?",
            (json.dumps(queue_data), session_id)
        )
        await self.db.commit()
        return {"status": "success"}

    async def add_followup_message(self, session_id: str, content: str) -> dict:
        """Add a follow-up message to the session's queue."""
        cursor = await self.db.execute(
            "SELECT queue_messages FROM sessions WHERE session_id = ?", (session_id,)
        )
        async with cursor:
            row = await cursor.fetchone()
        if not row:
            return {"status": "error", "message": "session not found"}
        queue_data = self._parse_queue_messages(row[0])
        msg = {"id": str(uuid.uuid4()), "content": content}
        queue_data["followup"].append(msg)
        await self.db.execute(
            "UPDATE sessions SET queue_messages = ? WHERE session_id = ?",
            (json.dumps(queue_data), session_id)
        )
        await self.db.commit()
        return {"status": "success", "message": msg}

    async def get_followup_queue(self, session_id: str) -> list:
        """Get all follow-up messages for a session."""
        cursor = await self.db.execute(
            "SELECT queue_messages FROM sessions WHERE session_id = ?", (session_id,)
        )
        async with cursor:
            row = await cursor.fetchone()
        if not row:
            return []
        queue_data = self._parse_queue_messages(row[0])
        return queue_data["followup"]

    async def remove_followup_message(self, session_id: str, message_id: str) -> dict:
        """Remove a follow-up message by id."""
        cursor = await self.db.execute(
            "SELECT queue_messages FROM sessions WHERE session_id = ?", (session_id,)
        )
        async with cursor:
            row = await cursor.fetchone()
        if not row:
            return {"status": "error", "message": "session not found"}
        queue_data = self._parse_queue_messages(row[0])
        queue_data["followup"] = [m for m in queue_data["followup"] if m["id"] != message_id]
        await self.db.execute(
            "UPDATE sessions SET queue_messages = ? WHERE session_id = ?",
            (json.dumps(queue_data), session_id)
        )
        await self.db.commit()
        return {"status": "success"}

    async def get_session(self, session_id: str) -> Optional[dict]:
        """Get session by ID."""
        cursor = await self.db.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        )
        async with cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))

    async def _get_session_model(self, session_id: str) -> Optional[str]:
        """Get the model configured for a session."""
        cursor = await self.db.execute(
            "SELECT model FROM sessions WHERE session_id = ?", (session_id,)
        )
        async with cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def _fetch_tool_calls(self, session_id: str) -> list[dict]:
        """Fetch and parse tool calls for a session."""
        cursor = await self.db.execute(
            "SELECT * FROM tool_calls WHERE session_id = ? ORDER BY created_at",
            (session_id,)
        )
        async with cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "call_id": tc[0],
                    "node_id": tc[1],
                    "session_id": tc[2],
                    "tool_name": tc[3],
                    "arguments": self._parse_json_field(tc[4], {}),
                    "result": self._parse_json_field(tc[5]),
                    "status": tc[6],
                    "created_at": tc[8],
                }
                for tc in rows
            ]

    async def _fetch_audit_logs(self, session_id: str) -> list[dict]:
        """Fetch audit logs for a session."""
        cursor = await self.db.execute(
            "SELECT * FROM audit_logs WHERE request_id LIKE ? ORDER BY timestamp",
            (f"%{session_id}%",)
        )
        async with cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "log_id": al[0],
                    "key_label": al[1],
                    "endpoint": al[2],
                    "method": al[3],
                    "status_code": al[4],
                    "client_ip": al[5],
                    "request_id": al[6],
                    "timestamp": al[7],
                }
                for al in rows
            ]

    async def export_trace(self, session_id: str) -> dict:
        """Export complete session trace: session metadata + all message nodes + tool calls + audit logs."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        nodes = await self.get_session_nodes(session_id)
        tool_calls_rows = await self._fetch_tool_calls(session_id)
        audit_rows = await self._fetch_audit_logs(session_id)

        return {
            "session_id": session_id,
            "workspace": session["workspace"],
            "model": session["model"],
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
            "metadata": self._parse_json_field(session["metadata"], {}),
            "nodes": [
                {
                    "node_id": n["node_id"],
                    "parent_node_id": n["parent_node_id"],
                    "role": n["role"],
                    "content": n["content"],
                    "tool_calls": self._parse_json_field(n["tool_calls"], []),
                    "tool_results": self._parse_json_field(n["tool_results"], []),
                    "compact_summary": n.get("compact_summary"),
                    "created_at": n["created_at"],
                }
                for n in nodes
            ],
            "tool_calls": tool_calls_rows,
            "audit_logs": audit_rows,
        }

    async def compact_session(self, session_id: str) -> dict:
        """Compress session history by marking old messages with LLM-generated summary.
        Does NOT delete any message_nodes — preserves full history."""
        nodes = await self.get_session_nodes(session_id)
        user_nodes = [n for n in nodes if n["role"] == "user"]
        if len(user_nodes) <= 3:
            return {"status": "skipped", "reason": "too_few_messages"}

        # Group: first half = history to compress, second half = recent context
        midpoint = len(user_nodes) // 2
        history_nodes = user_nodes[:midpoint]
        recent_nodes = user_nodes[midpoint:]

        # Build history text for summarization
        history_text = "\n".join(f"User: {n['content']}" for n in history_nodes)

        # Call LLM to summarize using the session's model provider
        mr = ModelRegistry()
        default_model = mr.get_default_model()
        session_model = model if (model := await self._get_session_model(session_id)) else default_model
        provider = mr.get_model_provider(session_model)

        if provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(model=session_model, temperature=0)
        elif provider in ("openai", "deepseek", "minimax"):
            from langchain_openai import ChatOpenAI
            key_env = {
                "openai": "OPENAI_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
                "minimax": "MINIMAX_API_KEY",
            }[provider]
            base_env = {
                "openai": None,
                "deepseek": None,
                "minimax": "MINIMAX_API_BASE",
            }[provider]
            import os
            llm = ChatOpenAI(
                model=session_model,
                api_key=os.getenv(key_env),
                base_url=os.getenv(base_env) if base_env else None,
                temperature=0,
            )
        else:
            return {"status": "error", "reason": f"Unknown provider: {provider}"}

        summary_prompt = f"Summarize this conversation history concisely:\n{history_text}"
        summary_result = await llm.ainvoke([HumanMessage(content=summary_prompt)])
        summary_text = summary_result.content

        # Mark old nodes as compacted (NOT deleted)
        for node in history_nodes:
            await self.db.execute(
                "UPDATE message_nodes SET compact_summary = ? WHERE node_id = ?",
                (summary_text, node["node_id"])
            )
        await self.db.commit()

        return {
            "status": "success",
            "messages_before": len(history_nodes),
            "messages_after": len(history_nodes),  # nodes NOT deleted, just marked
            "summary": summary_text,
        }