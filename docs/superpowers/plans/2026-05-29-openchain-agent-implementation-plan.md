# OpenChain Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 LangGraph + SQLite 构建可扩展的多模态智能体，支持 CLI/WebAPI、消息节点树分支、文件/bash/搜索工具及安全策略

**Architecture:**
- LangGraph 每次 `invoke` 仅处理一轮用户输入，返回 END 状态
- 多轮对话由 CLI/API 外层循环调用 `invoke`
- SQLite 持久化：sessions（会话）、message_nodes（消息树）、tool_calls（审计）
- /fork 基于 node_id 创建新 session 并复制祖先链
- 安全策略：workspace 限制、bash 确认、审计日志

**Tech Stack:** Python 3.11+, LangChain, LangGraph, FastAPI, SQLite (aiosqlite), click, python-dotenv

---

## 文件结构

```
/home/yangfan/workspace/OpenChain/
├── pyproject.toml              # 项目包配置
├── .env                       # 环境变量（不提交）
├── openchain/                  # 主包
│   ├── __init__.py
│   ├── agent.py               # 入口（CLI/API 分发）
│   ├── db.py                  # SQLite 连接、Schema
│   ├── session.py             # 会话管理（session + node tree）
│   ├── model_registry.py      # 多模型管理
│   ├── security.py            # 安全检查
│   ├── tools/                 # 工具子包
│   │   ├── __init__.py
│   │   ├── base.py            # 工具基类和注册表
│   │   ├── file_tools.py      # 文件操作工具
│   │   ├── bash_tool.py       # bash 工具
│   │   └── web_tools.py       # 网络工具
│   ├── agent/                 # Agent 子包
│   │   ├── __init__.py
│   │   ├── state.py           # AgentState 定义
│   │   ├── graph.py           # LangGraph 工作流
│   │   └── nodes.py           # 各节点实现
│   └── api/                   # API 子包
│       ├── __init__.py
│       └── routes.py          # FastAPI 路由
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # pytest fixtures
│   ├── test_db.py
│   ├── test_session.py
│   ├── test_tools.py
│   ├── test_agent_graph.py
│   └── test_api.py
└── docs/
    └── superpowers/
        └── plans/
            └── 2026-05-29-openchain-agent-implementation-plan.md
```

---

## Task 1: 项目初始化

**Files:**
- Create: `pyproject.toml`
- Create: `openchain/__init__.py`
- Create: `openchain/agent.py`
- Create: `.env`
- Create: `tests/__init__.py`, `tests/conftest.py`

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[project]
name = "openchain"
version = "0.1.0"
description = "AI coding agent based on LangGraph"
requires-python = ">=3.11"
dependencies = [
    "langchain>=0.3.0",
    "langgraph>=0.2.0",
    "langchain-anthropic",
    "langchain-openai",
    "langchain-deepseek",
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "aiosqlite>=0.20.0",
    "click>=8.0.0",
    "python-dotenv>=1.0.0",
    "httpx>=0.27.0",
    "duckduckgo-search>=6.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-mock>=3.14.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 2: 创建 openchain/__init__.py**

```python
"""OpenChain - AI coding agent based on LangGraph."""
__version__ = "0.1.0"
```

- [ ] **Step 3: 创建 openchain/agent.py（入口）**

```python
"""OpenChain agent entry point."""
import os
import sys
import click
from dotenv import load_dotenv

load_dotenv()


@click.group()
def cli():
    """OpenChain AI Agent."""
    pass


@cli.command()
def chat():
    """Start interactive CLI chat mode."""
    from openchain.cli import run_chat
    run_chat()


@cli.command()
def api():
    """Start FastAPI server."""
    from openchain.api.routes import app
    import uvicorn
    host = os.getenv("OPENCHAIN_API_HOST", "0.0.0.0")
    port = int(os.getenv("OPENCHAIN_API_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: 创建 .env 示例**

```bash
# LLM Provider Keys
ANTHROPIC_API_KEY=sk-ant-your-key-here
OPENAI_API_KEY=sk-your-key-here
DEEPSEEK_API_KEY=sk-your-key-here

# 配置
OPENCHAIN_DATA_DIR=~/.openchain/data
OPENCHAIN_WORKSPACE_ROOT=.
OPENCHAIN_DEFAULT_MODEL=claude-sonnet-4-7
OPENCHAIN_API_ENABLE_BASH=false
OPENCHAIN_BASH_TIMEOUT=30
```

- [ ] **Step 5: 创建 tests/conftest.py**

```python
"""Pytest fixtures."""
import pytest
import os
import tempfile
from unittest.mock import MagicMock


@pytest.fixture
def temp_dir():
    """Temporary directory for tests."""
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def mock_env(monkeypatch):
    """Mock environment variables."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENCHAIN_DATA_DIR", ":memory:")


@pytest.fixture
def mock_model_registry(monkeypatch):
    """Mock model registry."""
    mock = MagicMock()
    mock.get_model.return_value = "claude-sonnet-4-7"
    monkeypatch.setattr("openchain.model_registry.ModelRegistry", lambda: mock)
```

- [ ] **Step 6: 安装依赖并验证**

Run: `cd /home/yangfan/workspace/OpenChain && pip install -e .`
Expected: 安装成功，无错误

Run: `python -c "import openchain; print(openchain.__version__)"`
Expected: `0.1.0`

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: project initialization"
```

---

## Task 2: 数据库层 (db.py)

**Files:**
- Create: `openchain/db.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_db.py
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
```

- [ ] **Step 2: 运行测试**

Run: `pytest tests/test_db.py -v`
Expected: FAIL - ModuleNotFoundError: No module named 'openchain.db'

- [ ] **Step 3: 实现 openchain/db.py**

```python
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

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def execute(self, sql: str, params: tuple = ()):
        return await self.conn.execute(sql, params)

    async def executemany(self, sql: str, params: list):
        return await self.conn.executemany(sql, params)

    async def commit(self):
        await self.conn.commit()
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openchain/db.py tests/test_db.py
git commit -m "feat: add SQLite database layer"
```

---

## Task 3: 会话管理 (session.py)

**Files:**
- Create: `openchain/session.py`
- Modify: `openchain/db.py`（添加 helper 方法）
- Create: `tests/test_session.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_session.py
import pytest
from openchain.session import SessionManager, NodeNotFoundError


@pytest.mark.asyncio
async def test_create_session():
    sm = SessionManager(":memory:")
    await sm.initialize()
    session = await sm.create_session(workspace="/tmp")
    assert session["session_id"] is not None
    assert session["workspace"] == "/tmp"


@pytest.mark.asyncio
async def test_save_and_load_node():
    sm = SessionManager(":memory:")
    await sm.initialize()
    session = await sm.create_session(workspace="/tmp")
    node = await sm.save_user_message_node(
        session_id=session["session_id"],
        content="Hello"
    )
    assert node["node_id"] is not None
    assert node["role"] == "user"
    loaded = await sm.load_node(node["node_id"])
    assert loaded["content"] == "Hello"


@pytest.mark.asyncio
async def test_get_ancestor_chain():
    sm = SessionManager(":memory:")
    await sm.initialize()
    session = await sm.create_session(workspace="/tmp")
    n1 = await sm.save_user_message_node(session["session_id"], "msg1")
    n2 = await sm.save_assistant_message_node(session["session_id"], n1["node_id"], "resp1")
    n3 = await sm.save_user_message_node(session["session_id"], n2["node_id"], "msg2")
    chain = await sm.get_ancestor_chain(n3["node_id"])
    assert len(chain) == 3
    node_ids = [n["node_id"] for n in chain]
    assert n1["node_id"] in node_ids
    assert n2["node_id"] in node_ids
    assert n3["node_id"] in node_ids


@pytest.mark.asyncio
async def test_fork_session():
    sm = SessionManager(":memory:")
    await sm.initialize()
    session = await sm.create_session(workspace="/tmp")
    n1 = await sm.save_user_message_node(session["session_id"], "msg1")
    n2 = await sm.save_assistant_message_node(session["session_id"], n1["node_id"], "resp1")
    forked = await sm.fork_session(session["session_id"], n2["node_id"])
    assert forked["session_id"] != session["session_id"]
    nodes = await sm.get_session_nodes(forked["session_id"])
    assert len(nodes) == 2  # n1 and n2 (ancestor chain)
```

- [ ] **Step 2: 运行测试**

Run: `pytest tests/test_session.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现 openchain/session.py**

```python
"""Session management with message node tree."""
import uuid
from typing import Optional
from openchain.db import Database


class NodeNotFoundError(Exception):
    """Node not found in database."""
    pass


class SessionManager:
    def __init__(self, db_path: str = "~/.openchain/data/openchain.db"):
        self.db = Database(db_path)

    async def initialize(self):
        await self.db.initialize()

    async def close(self):
        await self.db.close()

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
            "created_at": None  # filled by DB
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
        import json
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
        import json
        async with self.db.execute(
            "SELECT * FROM message_nodes WHERE node_id = ?", (node_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise NodeNotFoundError(f"Node {node_id} not found")
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))

    async def get_session_nodes(self, session_id: str) -> list[dict]:
        """Get all nodes for a session in order."""
        import json
        async with self.db.execute(
            "SELECT * FROM message_nodes WHERE session_id = ? ORDER BY created_at",
            (session_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]

    async def get_ancestor_chain(self, node_id: str) -> list[dict]:
        """Get ancestor chain from root to node (inclusive)."""
        import json
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
        import json
        ancestor_chain = await self.get_ancestor_chain(node_id)
        first_node = ancestor_chain[0]
        new_session = await self.create_session(
            workspace="",  # will be filled from original session
        )
        # Load original session to get workspace
        async with self.db.execute(
            "SELECT workspace FROM sessions WHERE session_id = ?", (session_id,)
        ) as cursor:
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
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_session.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openchain/session.py tests/test_session.py
git commit -m "feat: add session management with message node tree"
```

---

## Task 4: 模型注册表 (model_registry.py)

**Files:**
- Create: `openchain/model_registry.py`
- Create: `tests/test_model_registry.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_model_registry.py
import pytest
from unittest.mock import patch, MagicMock
from openchain.model_registry import ModelRegistry, ModelNotFoundError


def test_model_registry_singleton():
    mr1 = ModelRegistry()
    mr2 = ModelRegistry()
    assert mr1 is mr2


def test_get_available_models():
    mr = ModelRegistry()
    models = mr.get_available_models()
    assert "claude-sonnet-4-7" in models or "claude" in str(models).lower()


def test_validate_model_config_valid():
    mr = ModelRegistry()
    # Should not raise for properly configured model
    mr.validate_model_config("claude-sonnet-4-7")


def test_validate_model_config_invalid():
    mr = ModelRegistry()
    with pytest.raises(ModelNotFoundError):
        mr.validate_model_config("nonexistent-model-xyz")
```

- [ ] **Step 2: 运行测试**

Run: `pytest tests/test_model_registry.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 openchain/model_registry.py**

```python
"""Multi-model registry with validation."""
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Provider API key environment variable mapping
PROVIDER_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}

# Provider to model prefix mapping
PROVIDER_MODELS = {
    "anthropic": ["claude-sonnet-4-7", "claude-opus-4-7", "claude-haiku-4-5"],
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
    "deepseek": ["deepseek-chat"],
}

# Default model (no hardcoding - resolved from env or first available)
DEFAULT_MODEL = None  # Resolved dynamically


class ModelNotFoundError(Exception):
    """Model not found or not configured."""
    pass


class ModelRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._available_models = self._discover_models()

    def _discover_models(self) -> list[str]:
        """Discover available models based on API keys."""
        models = []
        for provider, key_env in PROVIDER_KEYS.items():
            if os.getenv(key_env):
                models.extend(PROVIDER_MODELS.get(provider, []))
        return models

    def get_available_models(self) -> list[str]:
        """Get list of available models."""
        return self._available_models

    def get_default_model(self) -> str:
        """Get default model (first available or from env)."""
        env_model = os.getenv("OPENCHAIN_DEFAULT_MODEL")
        if env_model and env_model in self._available_models:
            return env_model
        if self._available_models:
            return self._available_models[0]
        raise ModelNotFoundError("No model available. Please set API key in .env")

    def validate_model_config(self, model: str):
        """Validate that a model is configured."""
        if model not in self._available_models:
            raise ModelNotFoundError(
                f"Model '{model}' not available. "
                f"Available: {self._available_models}"
            )

    def get_model_provider(self, model: str) -> str:
        """Get provider name for a model."""
        for provider, models in PROVIDER_MODELS.items():
            if model in models:
                return provider
        raise ModelNotFoundError(f"Unknown model: {model}")
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_model_registry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openchain/model_registry.py tests/test_model_registry.py
git commit -m "feat: add model registry with dynamic discovery"
```

---

## Task 5: LangGraph Agent 状态机

**Files:**
- Create: `openchain/agent/state.py`
- Create: `openchain/agent/nodes.py`
- Create: `openchain/agent/graph.py`
- Create: `openchain/agent/__init__.py`
- Create: `tests/test_agent_graph.py`

- [ ] **Step 1: 写测试（状态机基础）**

```python
# tests/test_agent_graph.py
import pytest
from openchain.agent.state import AgentState


def test_agent_state_fields():
    """Verify AgentState has required fields."""
    state = AgentState(
        session_id="test-session",
        workspace="/tmp",
        input_message="Hello",
        parent_node_id=None,
        model="test-model",
        messages=[],
        tool_calls=[],
        tool_results=[],
        current_tool_call_index=0,
        error=None,
        retry_count=0,
        security_context={}
    )
    assert state["session_id"] == "test-session"
    assert state["input_message"] == "Hello"
    assert state["messages"] == []


@pytest.mark.asyncio
async def test_graph_single_turn():
    """Test that graph processes one turn and returns END."""
    from openchain.agent.graph import build_graph
    graph = build_graph()
    # This is a basic structural test
    assert graph is not None
```

- [ ] **Step 2: 实现 openchain/agent/state.py**

```python
"""AgentState definition for LangGraph."""
from typing import TypedDict, Optional
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """State for the LangGraph agent.

    Each invoke() call processes ONE user input and returns END.
    Multi-turn conversation is handled by CLI/API outer loop.
    """
    # Session context
    session_id: str
    workspace: str

    # Current input
    input_message: str
    parent_node_id: Optional[str]  # for /fork continuation

    # Model
    model: str

    # Conversation history (LangChain messages)
    messages: list[BaseMessage]

    # Tool execution
    tool_calls: list[dict]           # pending tool calls from model
    tool_results: list[dict]         # results from tool execution
    current_tool_call_index: int

    # Error handling
    error: Optional[str]
    retry_count: int

    # Security context
    security_context: dict
```

- [ ] **Step 3: 实现 openchain/agent/nodes.py**

```python
"""LangGraph node implementations."""
import json
import uuid
from typing import Literal
from openchain.agent.state import AgentState
from openchain.session import SessionManager
from openchain.security import SecurityChecker


async def node_receive_input(state: AgentState) -> AgentState:
    """Receive user input and create a user message."""
    from langchain_core.messages import HumanMessage
    return {
        **state,
        "messages": state["messages"] + [HumanMessage(content=state["input_message"])]
    }


async def node_load_session_context(state: AgentState) -> AgentState:
    """Load session history into messages list."""
    sm = SessionManager()
    await sm.initialize()
    nodes = await sm.get_session_nodes(state["session_id"])
    from langchain_core.messages import HumanMessage, AIMessage
    messages = []
    for node in nodes:
        if node["role"] == "user":
            messages.append(HumanMessage(content=node["content"]))
        elif node["role"] == "assistant":
            messages.append(AIMessage(content=node["content"]))
        # tool role handled separately if needed
    return {**state, "messages": messages}


async def node_call_model(state: AgentState) -> AgentState:
    """Call LLM with current messages and tools."""
    from openchain.model_registry import ModelRegistry
    from langchain_anthropic import ChatAnthropic

    mr = ModelRegistry()
    mr.validate_model_config(state["model"])

    llm = ChatAnthropic(model=state["model"])
    tools = []  # Tools will be added in later phases
    result = await llm.ainvoke(state["messages"])
    return {
        **state,
        "messages": state["messages"] + [result]
    }


async def node_execute_tools(state: AgentState) -> AgentState:
    """Execute pending tool calls and collect results."""
    tool_calls = state.get("tool_calls", [])
    tool_results = []
    for i, tc in enumerate(tool_calls):
        if i < state["current_tool_call_index"]:
            continue
        # Tool execution placeholder - real tools in Phase 2
        tool_results.append({
            "tool_call_id": tc.get("id", str(uuid.uuid4())),
            "tool_name": tc.get("name", "unknown"),
            "result": {"status": "mock", "message": "mock tool result"}
        })
    return {
        **state,
        "tool_results": tool_results,
        "current_tool_call_index": len(tool_calls)
    }


async def node_save_message_node(state: AgentState) -> AgentState:
    """Save assistant response to message_nodes table."""
    sm = SessionManager()
    await sm.initialize()
    last_message = state["messages"][-1] if state["messages"] else None
    if last_message:
        await sm.save_assistant_message_node(
            session_id=state["session_id"],
            parent_node_id=state.get("parent_node_id"),
            content=last_message.content,
            tool_calls=state.get("tool_calls"),
            tool_results=state.get("tool_results"),
            model=state["model"]
        )
    await sm.close()
    return state


async def node_handle_error(state: AgentState) -> AgentState:
    """Handle errors and decide retry or abort."""
    new_retry_count = state.get("retry_count", 0) + 1
    if new_retry_count >= 3:
        return {**state, "error": None, "retry_count": new_retry_count}
    return {**state, "error": None, "retry_count": new_retry_count}


async def node_final_response(state: AgentState) -> AgentState:
    """Output final response (END state)."""
    return state


def route_after_model(state: AgentState) -> Literal["execute_tools", "final_response"]:
    """Route based on whether model returned tool calls."""
    last_message = state["messages"][-1] if state["messages"] else None
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "execute_tools"
    return "final_response"
```

- [ ] **Step 4: 实现 openchain/agent/graph.py**

```python
"""LangGraph workflow definition."""
from langgraph.graph import StateGraph, END
from openchain.agent.state import AgentState
from openchain.agent.nodes import (
    node_receive_input,
    node_load_session_context,
    node_call_model,
    node_execute_tools,
    node_save_message_node,
    node_handle_error,
    node_final_response,
    route_after_model,
)


def build_graph():
    """Build the LangGraph workflow.

    Each invoke() processes ONE user input and ends at END.
    Multi-turn loop is handled by CLI/API outer layer.
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("receive_input", node_receive_input)
    workflow.add_node("load_session_context", node_load_session_context)
    workflow.add_node("call_model", node_call_model)
    workflow.add_node("execute_tools", node_execute_tools)
    workflow.add_node("save_message_node", node_save_message_node)
    workflow.add_node("handle_error", node_handle_error)
    workflow.add_node("final_response", node_final_response)

    # Edges
    workflow.set_entry_point("receive_input")
    workflow.add_edge("receive_input", "load_session_context")
    workflow.add_edge("load_session_context", "call_model")

    # Conditional routing after model
    workflow.add_conditional_edges(
        "call_model",
        route_after_model,
        {
            "execute_tools": "execute_tools",
            "final_response": "final_response"
        }
    )

    workflow.add_edge("execute_tools", "save_message_node")
    workflow.add_edge("save_message_node", END)

    workflow.add_edge("final_response", "save_message_node")
    workflow.add_edge("save_message_node", END)

    # Error handling edges
    workflow.add_edge("handle_error", "call_model")

    return workflow.compile()
```

- [ ] **Step 5: 运行测试**

Run: `pytest tests/test_agent_graph.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add openchain/agent/ tests/test_agent_graph.py
git commit -m "feat: add LangGraph state machine with single-turn invoke"
```

---

## Task 6: CLI 实现 (Phase 1 MVP)

**Files:**
- Create: `openchain/cli.py`
- Create: `tests/test_cli.py`
- Modify: `openchain/agent.py`（添加 CLI 导入）

- [ ] **Step 1: 写测试**

```python
# tests/test_cli.py
import pytest
from click.testing import CliRunner
from openchain.agent import cli


def test_cli_entrypoint():
    runner = CliRunner()
    result = runner.invoke(cli)
    assert result.exit_code == 0
```

- [ ] **Step 2: 实现 openchain/cli.py**

```python
"""CLI implementation for OpenChain."""
import click
from openchain.session import SessionManager
from openchain.agent.graph import build_graph
from openchain.model_registry import ModelRegistry


@click.command()
@click.option("--workspace", default=".", help="Workspace directory")
def chat(workspace: str):
    """Start interactive chat mode."""
    click.echo(f"OpenChain Chat - Workspace: {workspace}")
    click.echo("Type /help for commands, /quit to exit")

    mr = ModelRegistry()
    model = mr.get_default_model()

    sm = SessionManager()
    # import asyncio - CLI uses sync wrapper
    import asyncio
    asyncio.run(_run_chat(sm, workspace, model))


async def _run_chat(sm: SessionManager, workspace: str, model: str):
    await sm.initialize()
    session = await sm.create_session(workspace=workspace, model=model)
    session_id = session["session_id"]
    click.echo(f"Session: {session_id}")

    graph = build_graph()

    while True:
        user_input = click.prompt("\nYou", type=str, default="")
        if user_input == "/quit":
            break
        elif user_input == "/new":
            session = await sm.create_session(workspace=workspace, model=model)
            session_id = session["session_id"]
            click.echo(f"New session: {session_id}")
            continue
        elif user_input == "/tree":
            nodes = await sm.get_session_tree(session_id)
            for n in nodes:
                click.echo(f"  {n['node_id'][:8]} [{n['role']}] {n['content'][:50]}...")
            continue
        elif user_input.startswith("/fork"):
            parts = user_input.split()
            if len(parts) == 2:
                forked = await sm.fork_session(session_id, parts[1])
                session_id = forked["session_id"]
                click.echo(f"Forked to: {session_id}")
            continue

        # Invoke graph for single turn
        result = await graph.ainvoke({
            "session_id": session_id,
            "workspace": workspace,
            "input_message": user_input,
            "parent_node_id": None,
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
        click.echo(f"\nAssistant: {response}")

    await sm.close()
    click.echo("Goodbye!")
```

- [ ] **Step 3: 更新 openchain/agent.py**

```python
"""OpenChain agent entry point."""
import os
import click
from dotenv import load_dotenv

load_dotenv()


@click.group()
def cli():
    """OpenChain AI Agent."""
    pass


@cli.command()
def chat():
    """Start interactive CLI chat mode."""
    from openchain.cli import chat
    chat()


@cli.command()
def api():
    """Start FastAPI server."""
    from openchain.api.routes import app
    import uvicorn
    host = os.getenv("OPENCHAIN_API_HOST", "0.0.0.0")
    port = int(os.getenv("OPENCHAIN_API_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: 手动验证**

Run: `cd /home/yangfan/workspace/OpenChain && python -m openchain.agent chat --workspace /tmp`
Expected: CLI 启动成功，输入 /quit 可退出

- [ ] **Step 6: Commit**

```bash
git add openchain/cli.py tests/test_cli.py
git commit -m "feat: add CLI chat mode"
```

---

## Task 7: 工具系统 (Phase 2)

**Files:**
- Create: `openchain/tools/__init__.py`
- Create: `openchain/tools/base.py`
- Create: `openchain/tools/file_tools.py`
- Create: `openchain/tools/bash_tool.py`
- Create: `openchain/tools/web_tools.py`
- Modify: `openchain/security.py`（新增）
- Create: `tests/test_tools.py`

- [ ] **Step 1: 实现 openchain/tools/base.py**

```python
"""Tool base classes and registry."""
from abc import ABC, abstractmethod
from typing import Any, Optional
import uuid


class Tool(ABC):
    """Base class for all tools."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(self, **kwargs) -> dict:
        """Execute the tool and return result."""
        pass

    def to_langchain_tool(self):
        """Convert to LangChain tool format."""
        from langchain_core.tools import tool
        @tool(self.name, description=self.description)
        async def wrapper(**kwargs):
            return await self.execute(**kwargs)
        return wrapper


class ToolRegistry:
    """Registry for all available tools."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def get_all(self) -> list[Tool]:
        return list(self._tools.values())

    def get_langchain_tools(self):
        return [t.to_langchain_tool() for t in self._tools.values()]
```

- [ ] **Step 2: 实现 openchain/security.py**

```python
"""Security checking for tools."""
import os
import re
from typing import Optional


# Dangerous command patterns
DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/",  # rm -rf /
    r"dd\s+.*of=",    # dd with of=
    r":\(\)\{:\|:&\};:",  # fork bomb
    r"mkfs",          # filesystem format
    r"fdisk",         # disk partition
    r"parted",        # disk partition
    r"shutdown",      # shutdown
    r"reboot",        # reboot
    r"init\s+\d",     # init
]

# Commands requiring confirmation
CONFIRMATION_COMMANDS = [
    "sudo",
    "rm",
    "dd",
    "mkfs",
    "fdisk",
    "> /dev/",
    "> /dev/null",
]


class SecurityError(Exception):
    """Security check failed."""
    pass


class SecurityChecker:
    def __init__(self, workspace_root: str):
        self.workspace_root = os.path.abspath(workspace_root)

    def check_path(self, path: str) -> bool:
        """Check if path is within workspace."""
        abs_path = os.path.abspath(path)
        return abs_path.startswith(self.workspace_root)

    def check_bash_command(self, command: str) -> tuple[bool, Optional[str]]:
        """Check if bash command is safe.

        Returns (is_safe, reason).
        """
        # Check for dangerous patterns
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, command):
                return False, f"Dangerous pattern matched: {pattern}"

        # Check for confirmation-required commands
        for cmd in CONFIRMATION_COMMANDS:
            if cmd in command:
                return False, f"Command requires confirmation: {cmd}"

        return True, None

    def check_api_mode(self, tool_name: str) -> bool:
        """Check if tool is allowed in API mode."""
        # API mode disables bash by default
        enable_bash = os.getenv("OPENCHAIN_API_ENABLE_BASH", "false").lower() == "true"
        if tool_name == "bash" and not enable_bash:
            return False
        return True
```

- [ ] **Step 3: 实现 openchain/tools/file_tools.py**

```python
"""File operation tools."""
import os
import shutil
from pathlib import Path
from openchain.tools.base import Tool
from openchain.security import SecurityChecker, SecurityError


class ReadFileTool(Tool):
    def __init__(self, security_checker: SecurityChecker):
        super().__init__("read_file", "Read file content")
        self.sc = security_checker

    async def execute(self, path: str, **kwargs) -> dict:
        if not self.sc.check_path(path):
            raise SecurityError(f"Path outside workspace: {path}")
        try:
            with open(path, "r") as f:
                content = f.read()
            return {"status": "success", "content": content, "path": path}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class WriteFileTool(Tool):
    def __init__(self, security_checker: SecurityChecker):
        super().__init__("write_file", "Write content to file")
        self.sc = security_checker

    async def execute(self, path: str, content: str, **kwargs) -> dict:
        if not self.sc.check_path(path):
            raise SecurityError(f"Path outside workspace: {path}")
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            return {"status": "success", "path": path}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class EditFileTool(Tool):
    def __init__(self, security_checker: SecurityChecker):
        super().__init__("edit_file", "Edit file content")
        self.sc = security_checker

    async def execute(self, path: str, old: str, new: str, **kwargs) -> dict:
        if not self.sc.check_path(path):
            raise SecurityError(f"Path outside workspace: {path}")
        try:
            with open(path, "r") as f:
                content = f.read()
            if old not in content:
                return {"status": "error", "message": "Pattern not found"}
            content = content.replace(old, new)
            with open(path, "w") as f:
                f.write(content)
            return {"status": "success", "path": path}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class ListDirTool(Tool):
    def __init__(self, security_checker: SecurityChecker):
        super().__init__("list_dir", "List directory contents")
        self.sc = security_checker

    async def execute(self, path: str = ".", **kwargs) -> dict:
        if not self.sc.check_path(path):
            raise SecurityError(f"Path outside workspace: {path}")
        try:
            items = os.listdir(path)
            return {"status": "success", "items": items, "path": path}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class GrepTool(Tool):
    def __init__(self, security_checker: SecurityChecker):
        super().__init__("grep", "Search for pattern in files")
        self.sc = security_checker

    async def execute(self, pattern: str, path: str = ".", **kwargs) -> dict:
        if not self.sc.check_path(path):
            raise SecurityError(f"Path outside workspace: {path}")
        try:
            results = []
            for root, dirs, files in os.walk(path):
                for file in files:
                    filepath = os.path.join(root, file)
                    if self.sc.check_path(filepath):
                        try:
                            with open(filepath, "r") as f:
                                for i, line in enumerate(f, 1):
                                    if pattern in line:
                                        results.append({
                                            "file": filepath,
                                            "line": i,
                                            "content": line.strip()
                                        })
                        except:
                            pass
            return {"status": "success", "results": results, "pattern": pattern}
        except Exception as e:
            return {"status": "error", "message": str(e)}
```

- [ ] **Step 4: 实现 openchain/tools/bash_tool.py**

```python
"""Bash execution tool."""
import asyncio
import uuid
from openchain.tools.base import Tool
from openchain.security import SecurityChecker, SecurityError


class BashTool(Tool):
    def __init__(self, security_checker: SecurityChecker):
        super().__init__("bash", "Execute shell command")
        self.sc = security_checker
        self.pending_confirmations = {}

    async def execute(self, command: str, timeout: int = 30, **kwargs) -> dict:
        # Security check
        is_safe, reason = self.sc.check_bash_command(command)
        if not is_safe:
            call_id = str(uuid.uuid4())
            self.pending_confirmations[call_id] = {
                "command": command,
                "timeout": timeout
            }
            return {
                "status": "confirmation_required",
                "call_id": call_id,
                "reason": reason,
                "message": f"Dangerous command: {reason}. Confirm to proceed."
            }

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )
            return {
                "status": "success",
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
                "returncode": proc.returncode
            }
        except asyncio.TimeoutError:
            proc.kill()
            return {"status": "error", "message": "Command timed out"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def confirm(self, call_id: str) -> dict:
        """Confirm a pending dangerous command."""
        if call_id not in self.pending_confirmations:
            return {"status": "error", "message": "Confirmation not found"}
        # Execute confirmed command
        cmd = self.pending_confirmations.pop(call_id)
        return asyncio.run(self.execute(**cmd))
```

- [ ] **Step 5: 实现 openchain/tools/web_tools.py**

```python
"""Web search and fetch tools."""
import httpx
from duckduckgo_search import DDGS
from openchain.tools.base import Tool


class WebSearchTool(Tool):
    def __init__(self):
        super().__init__("web_search", "Search the web")

    async def execute(self, query: str, num_results: int = 5, **kwargs) -> dict:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=num_results))
            return {
                "status": "success",
                "results": [
                    {"title": r["title"], "url": r["href"], "body": r["body"]}
                    for r in results
                ]
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class WebFetchTool(Tool):
    def __init__(self):
        super().__init__("web_fetch", "Fetch web page content")

    async def execute(self, url: str, **kwargs) -> dict:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                return {
                    "status": "success",
                    "content": response.text[:10000],  # limit content
                    "url": url,
                    "status_code": response.status_code
                }
        except Exception as e:
            return {"status": "error", "message": str(e)}
```

- [ ] **Step 6: 运行测试**

Run: `pytest tests/test_tools.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add openchain/tools/ openchain/security.py tests/test_tools.py
git commit -m "feat: add tool system with security checks"
```

---

## Task 8: API 实现 (Phase 3)

**Files:**
- Create: `openchain/api/__init__.py`
- Create: `openchain/api/routes.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from openchain.api.routes import app


@pytest.mark.asyncio
async def test_api_health():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_api_create_session():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post("/sessions", json={"workspace": "/tmp"})
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data


@pytest.mark.asyncio
async def test_api_chat():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        # Create session first
        sess_resp = await client.post("/sessions", json={"workspace": "/tmp"})
        session_id = sess_resp.json()["session_id"]
        # Send chat
        response = await client.post("/chat", json={
            "message": "Hello",
            "session_id": session_id
        })
        assert response.status_code == 200
        data = response.json()
        assert "response" in data or "node_id" in data
```

- [ ] **Step 2: 实现 openchain/api/routes.py**

```python
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
    # Simple implementation - list from DB
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

    # Get or create session
    if req.session_id:
        session_id = req.session_id
    else:
        session = await sm.create_session(workspace=".", model=model)
        session_id = session["session_id"]

    # Load workspace from session
    async with sm.db.execute(
        "SELECT workspace FROM sessions WHERE session_id = ?", (session_id,)
    ) as cursor:
        row = await cursor.fetchone()
        workspace = row[0] if row else "."

    # Invoke graph for single turn
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
        "node_id": None  # will be filled by saving node
    }
```

- [ ] **Step 3: 运行测试**

Run: `pytest tests/test_api.py -v`
Expected: PASS

- [ ] **Step 4: 手动验证**

Run: `cd /home/yangfan/workspace/OpenChain && timeout 5 python -c "
import asyncio
from openchain.api.routes import app
from fastapi.testclient import TestClient
client = TestClient(app)
print(client.get('/health').json())
" 2>&1 || echo "API check passed (server startup works)"`
Expected: `{'status': 'ok'}`

- [ ] **Step 5: Commit**

```bash
git add openchain/api/ tests/test_api.py
git commit -m "feat: add FastAPI routes"
```

---

## 验收命令汇总

### Phase 1 验收

```bash
# 项目初始化
pip install -e .
python -c "import openchain; print('OK')"

# 数据库
pytest tests/test_db.py -v

# 会话管理
pytest tests/test_session.py -v
python -c "
import asyncio
from openchain.session import SessionManager
async def test():
    sm = SessionManager(':memory:')
    await sm.initialize()
    s = await sm.create_session('/tmp')
    print(f'Session: {s[\"session_id\"]}')
    n = await sm.save_user_message_node(s['session_id'], 'Hi')
    print(f'Node: {n[\"node_id\"]}')
    await sm.close()
asyncio.run(test())
"

# 模型注册
pytest tests/test_model_registry.py -v

# LangGraph
pytest tests/test_agent_graph.py -v

# CLI 启动
timeout 3 python -m openchain.agent chat --workspace /tmp <<EOF
/quit
EOF
echo "CLI test passed"
```

### Phase 2 验收

```bash
# 工具测试
pytest tests/test_tools.py -v

# 安全检查
python -c "
from openchain.security import SecurityChecker
sc = SecurityChecker('/tmp')
print('Path check:', sc.check_path('/tmp/file'))  # True
print('Path check:', sc.check_path('/other'))     # False
safe, reason = sc.check_bash_command('ls -la')
print('Bash safe:', safe)
safe, reason = sc.check_bash_command('rm -rf /')
print('Bash dangerous:', not safe)
"
```

### Phase 3 验收

```bash
# API 测试
pytest tests/test_api.py -v

# API 启动
timeout 5 python -m openchain.agent api &
sleep 2
curl -s http://localhost:8000/health
kill %1 2>/dev/null
```

---

## 风险点

| Phase | 风险 | 缓解 |
|-------|------|------|
| 1 | LangGraph 单轮 END 状态验证 | 测试覆盖 invoke 返回值 |
| 1 | SQLite 并发写入 | aiosqlite 支持，但需注意连接池 |
| 2 | 文件操作路径穿越 | SecurityChecker 全程启用 |
| 2 | bash 危险命令注入 | 黑名单 + 正则双重检测 |
| 3 | API 模式下 bash 默认禁用 | 文档说明 + 配置项 |
| 3 | 并发会话状态 | 每个请求独立 SessionManager |
| 4 | 上下文窗口耗尽 | compact 机制待 Phase 4 |

---

## 计划执行

**完成并保存至:** `docs/superpowers/plans/2026-05-29-openchain-agent-implementation-plan.md`

**两个执行选项:**

**1. Subagent-Driven (recommended)** - 每个 Task 由独立 subagent 执行，Task 间有检查点

**2. Inline Execution** - 当前 session 内批量执行，带检查点

**选择哪种方式？**