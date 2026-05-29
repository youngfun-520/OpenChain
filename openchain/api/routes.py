"""FastAPI routes for OpenChain API."""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from openchain.session import SessionManager
from openchain.agent.graph import build_graph
from openchain.model_registry import ModelRegistry


app = FastAPI(title="OpenChain API")


class CreateSessionRequest(BaseModel):
    workspace: str = "."
    model: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    parent_node_id: Optional[str] = None


class ForkRequest(BaseModel):
    node_id: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/sessions")
async def list_sessions():
    """List all sessions."""
    sm = SessionManager()
    await sm.initialize()
    sessions = []
    async with sm.db.execute("SELECT * FROM sessions ORDER BY created_at DESC") as cursor:
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        sessions = [dict(zip(columns, row)) for row in rows]
    await sm.close()
    return {"sessions": sessions}


@app.post("/sessions")
async def create_session(req: CreateSessionRequest):
    """Create new session."""
    mr = ModelRegistry()
    model = req.model or mr.get_default_model()
    sm = SessionManager()
    await sm.initialize()
    session = await sm.create_session(workspace=req.workspace, model=model)
    await sm.close()
    return session


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session info."""
    sm = SessionManager()
    await sm.initialize()
    async with sm.db.execute(
        "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            await sm.close()
            raise HTTPException(status_code=404, detail="Session not found")
        columns = [desc[0] for desc in cursor.description]
        session = dict(zip(columns, row))
    await sm.close()
    return session


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete session."""
    sm = SessionManager()
    await sm.initialize()
    await sm.db.execute("DELETE FROM message_nodes WHERE session_id = ?", (session_id,))
    await sm.db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    await sm.db.commit()
    await sm.close()
    return {"status": "deleted"}


@app.get("/sessions/{session_id}/tree")
async def get_session_tree(session_id: str):
    """Get session tree structure."""
    sm = SessionManager()
    await sm.initialize()
    nodes = await sm.get_session_tree(session_id)
    await sm.close()
    return {"session_id": session_id, "nodes": nodes}


@app.post("/sessions/{session_id}/fork")
async def fork_session(session_id: str, req: ForkRequest):
    """Fork session from a node."""
    sm = SessionManager()
    await sm.initialize()
    forked = await sm.fork_session(session_id, req.node_id)
    await sm.close()
    return forked


@app.post("/chat")
async def chat(req: ChatRequest):
    """Send chat message."""
    mr = ModelRegistry()
    model = mr.get_default_model()
    sm = SessionManager()
    await sm.initialize()

    if req.session_id:
        session_id = req.session_id
    else:
        session = await sm.create_session(workspace=".", model=model)
        session_id = session["session_id"]

    cursor = await sm.db.execute(
        "SELECT workspace FROM sessions WHERE session_id = ?", (session_id,)
    )
    async with cursor:
        row = await cursor.fetchone()
        workspace = row[0] if row else "."

    graph = build_graph()
    result = await graph.ainvoke({
        "session_id": session_id,
        "workspace": workspace,
        "input_message": req.message,
        "parent_node_id": req.parent_node_id,
        "model": model,
        "messages": [],
        "tool_calls": [],
        "tool_results": [],
        "current_tool_call_index": 0,
        "error": None,
        "retry_count": 0,
        "security_context": {"workspace_root": workspace}
    })

    await sm.close()

    response = result["messages"][-1].content if result["messages"] else ""
    return {
        "session_id": session_id,
        "response": response,
        "node_id": None
    }