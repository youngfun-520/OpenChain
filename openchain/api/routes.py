"""FastAPI routes for OpenChain API."""
from fastapi import FastAPI, HTTPException, Security, Depends
from pydantic import BaseModel
from typing import Optional
from openchain.session import SessionManager
from openchain.agent.graph import build_graph
from openchain.model_registry import ModelRegistry
from openchain.api.auth import verify_api_key, require_scope


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


@app.get("/sessions", dependencies=[Security(verify_api_key)])
async def list_sessions():
    """List all sessions."""
    async with SessionManager() as sm:
        sessions = await sm.list_sessions()
    return {"sessions": sessions}


@app.post("/sessions", dependencies=[Security(verify_api_key)])
async def create_session(req: CreateSessionRequest):
    """Create new session."""
    mr = ModelRegistry()
    model = req.model or mr.get_default_model()
    async with SessionManager() as sm:
        session = await sm.create_session(workspace=req.workspace, model=model)
    return session


@app.get("/sessions/{session_id}", dependencies=[Security(verify_api_key)])
async def get_session(session_id: str):
    """Get session info."""
    async with SessionManager() as sm:
        async with sm.db.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Session not found")
            columns = [desc[0] for desc in cursor.description]
            session = dict(zip(columns, row))
    return session


class SessionUpdate(BaseModel):
    model: Optional[str] = None


@app.patch("/sessions/{session_id}", dependencies=[Security(verify_api_key)])
async def update_session(
    session_id: str,
    update: SessionUpdate,
    _: str = Depends(require_scope("write")),
):
    """Update session model."""
    if update.model is None:
        raise HTTPException(status_code=400, detail="Model cannot be null")
    mr = ModelRegistry()
    try:
        mr.validate_model_config(update.model)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    async with SessionManager() as sm:
        try:
            await sm.update_session_model(session_id, update.model)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        session = await sm.get_session(session_id)
        return session


@app.delete("/sessions/{session_id}", dependencies=[Security(verify_api_key)])
async def delete_session(session_id: str):
    """Delete session."""
    async with SessionManager() as sm:
        await sm.db.execute("DELETE FROM message_nodes WHERE session_id = ?", (session_id,))
        await sm.db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        await sm.db.commit()
    return {"status": "deleted"}


@app.get("/sessions/{session_id}/tree", dependencies=[Security(verify_api_key)])
async def get_session_tree(session_id: str):
    """Get session tree structure."""
    async with SessionManager() as sm:
        nodes = await sm.get_session_tree(session_id)
    return {"session_id": session_id, "nodes": nodes}


@app.get("/sessions/{session_id}/trace", dependencies=[Security(verify_api_key)])
async def get_session_trace(
    session_id: str,
    _: str = Depends(require_scope("read")),
):
    """Get full session trace including nodes, tool calls, and audit logs."""
    async with SessionManager() as sm:
        try:
            trace = await sm.export_trace(session_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return trace


@app.post("/sessions/{session_id}/fork", dependencies=[Security(verify_api_key)])
async def fork_session(session_id: str, req: ForkRequest):
    """Fork session from a node."""
    async with SessionManager() as sm:
        forked = await sm.fork_session(session_id, req.node_id)
    return forked


@app.post("/chat", dependencies=[Security(verify_api_key)])
async def chat(req: ChatRequest):
    """Send chat message."""
    mr = ModelRegistry()
    model = mr.get_default_model()

    async with SessionManager() as sm:
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

    response = result["messages"][-1].content if result["messages"] else ""
    return {
        "session_id": session_id,
        "response": response,
        "node_id": None
    }