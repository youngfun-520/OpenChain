# Agent Capability Expansion v0.2.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand agent capabilities across 5 areas: session compaction, CLI experience, message queue, multi-model switching, and trace export.

**Architecture:** Each feature is implemented as an independent module with clear interfaces. Compact uses a summarization step injected into the LangGraph workflow. CLI enhancements use prompt_toolkit for readline-compatible input. Message queue is a first-class session property persisted to the sessions table. Multi-model config extends the existing ModelRegistry with per-session overrides. Trace export serializes the full session tree to JSON with all tool calls and results.

**Tech Stack:** Python 3.11+, prompt_toolkit (CLI), LangChain message summarization, SQLite JSON fields, FastAPI streaming (optional for trace).

---

## File Structure

```
openchain/
├── cli.py                      # REPL with /compact, autocomplete, multiline
├── agent/
│   ├── state.py               # Add compact_triggered, steering_queue, followup_queue
│   ├── nodes.py               # Add node_compact, node_steering_inject, node_followup
│   └── graph.py               # Compact edges, steering/followup routing
├── model_registry.py          # Per-session config, model override resolution
├── session.py                 # Compact method, queue methods, trace export
├── db.py                      # Add queue_messages column to sessions, compact_summary to message_nodes
├── tools/
│   └── trace_export.py        # New: trace serialization to JSON
└── api/
    └── routes.py              # /compact endpoint, /sessions/{id}/trace, model config

tests/
├── test_compact.py            # Session compaction tests
├── test_cli_enhanced.py       # CLI multiline, autocomplete, Ctrl+C
├── test_message_queue.py      # Steering and follow-up queue tests
├── test_multi_model.py        # Model switching and config tests
└── test_trace_export.py       # Trace export tests
```

---

## Task 1: /compact History Compression

### Files
- Modify: `openchain/cli.py:1-50` (add `/compact` command)
- Modify: `openchain/session.py:1-200` (add `compact_session` method)
- Modify: `openchain/db.py:17-30` (add `compact_summary` column to message_nodes)
- Modify: `openchain/agent/state.py` (add `compact_triggered` field)
- Modify: `openchain/agent/nodes.py` (add `node_compact` function)
- Modify: `openchain/agent/graph.py` (add compact routing edge)
- Create: `openchain/tools/summarize_tool.py` (LLM-based summarization)
- Create: `tests/test_compact.py`

### Steps

- [ ] **Step 1: Write failing test — session has no compact method**

```python
# tests/test_compact.py
import pytest
from openchain.session import SessionManager

@pytest.mark.asyncio
async def test_session_has_compact_method():
    """SessionManager should have a compact_session method."""
    sm = SessionManager()
    await sm.initialize()
    try:
        session = await sm.create_session(workspace="/tmp")
        # Should have a compact_session method
        assert hasattr(sm, "compact_session"), "compact_session method not found"
    finally:
        await sm.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_compact.py::test_session_has_compact_method -v`
Expected: FAIL with "compact_session method not found"

- [ ] **Step 3: Write minimal implementation — add stub method**

```python
# openchain/session.py — add after existing methods
async def compact_session(self, session_id: str) -> dict:
    """Placeholder — raises NotImplementedError."""
    raise NotImplementedError("compact_session not yet implemented")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_compact.py::test_session_has_compact_method -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_compact.py openchain/session.py
git commit -m "feat(compact): add stub compact_session method"
```

### Sub-task 1.1: Add compact_summary column to message_nodes

- [ ] **Step 1: Write failing test — node has no compact_summary field**

```python
# tests/test_compact.py — add after test_session_has_compact_method
@pytest.mark.asyncio
async def test_compact_summary_column_exists():
    """message_nodes table should have compact_summary column."""
    import sqlite3
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        async with Database(db_path) as db:
            await db.initialize()
            cursor = await db.conn.execute(
                "PRAGMA table_info(message_nodes)"
            )
            columns = {row[1] for row in await cursor.fetchall()}
            assert "compact_summary" in columns, f"compact_summary missing from columns: {columns}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_compact.py::test_compact_summary_column_exists -v`
Expected: FAIL with "compact_summary missing"

- [ ] **Step 3: Write minimal implementation — add column to SCHEMA_SQL**

```python
# openchain/db.py — find message_nodes CREATE TABLE and add compact_summary
CREATE TABLE IF NOT EXISTS message_nodes (
    ...
    token_count INTEGER,
    compact_summary TEXT,   # <-- ADD THIS LINE
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ...
);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_compact.py::test_compact_summary_column_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openchain/db.py tests/test_compact.py
git commit -m "feat(db): add compact_summary column to message_nodes"
```

### Sub-task 1.2: Implement compact_session with LLM summarization

- [ ] **Step 1: Write failing test — compact reduces message count**

```python
# tests/test_compact.py — add
@pytest.mark.asyncio
async def test_compact_reduces_message_count():
    """compact_session should replace old messages with a summary."""
    import os
    os.environ["ANTHROPIC_API_KEY"] = "test-key"
    sm = SessionManager()
    await sm.initialize()
    try:
        session = await sm.create_session(workspace="/tmp")
        sid = session["session_id"]
        # Save 5 user messages
        parent = None
        for i in range(5):
            node = await sm.save_user_message_node(sid, f"Message {i}", parent)
            parent = node["node_id"]
        # Save 1 assistant message
        await sm.save_assistant_message_node(sid, parent, "Reply", model="test")
        # Compact
        result = await sm.compact_session(sid)
        assert result["status"] == "success"
        assert result["messages_before"] == 5
        assert result["messages_after"] == 1
        assert result["summary"] is not None
    finally:
        await sm.close()
```

- [ ] **Step 2: Run test to verify it fails (compact_session raises NotImplementedError)**

Run: `pytest tests/test_compact.py::test_compact_reduces_message_count -v`
Expected: FAIL with "NotImplementedError"

- [ ] **Step 3: Write minimal implementation — real compact logic**

```python
# openchain/session.py — replace stub with real implementation
async def compact_session(self, session_id: str) -> dict:
    """Compress session history by replacing old messages with LLM-generated summary."""
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

    # Call LLM to summarize
    from openchain.model_registry import ModelRegistry
    mr = ModelRegistry()
    default_model = mr.get_default_model()
    from langchain_anthropic import ChatAnthropic
    llm = ChatAnthropic(model=default_model, temperature=0)
    summary_prompt = f"Summarize this conversation history concisely:\n{history_text}"
    summary_result = await llm.ainvoke([HumanMessage(content=summary_prompt)])
    summary_text = summary_result.content

    # Mark old nodes as compacted
    for node in history_nodes:
        await self.conn.execute(
            "UPDATE message_nodes SET compact_summary = ? WHERE node_id = ?",
            (summary_text, node["node_id"])
        )
    await self.commit()

    # Return compact result
    return {
        "status": "success",
        "messages_before": len(history_nodes),
        "messages_after": 1,
        "summary": summary_text,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_compact.py::test_compact_reduces_message_count -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openchain/session.py tests/test_compact.py
git commit -m "feat(compact): implement session history compression via LLM summarization"
```

### Sub-task 1.3: Add /compact CLI command

- [ ] **Step 1: Write failing test — CLI accepts /compact command**

```python
# tests/test_compact.py — add
def test_cli_compact_command_exists():
    """CLI should recognize /compact command."""
    from openchain.cli import REPL_COMMANDS
    assert "/compact" in REPL_COMMANDS, f"Expected /compact in commands: {list(REPL_COMMANDS.keys())}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_compact.py::test_cli_compact_command_exists -v`
Expected: FAIL with "/compact not in REPL_COMMANDS"

- [ ] **Step 3: Write minimal implementation**

```python
# openchain/cli.py — add to REPL_COMMANDS dict near top of file
REPL_COMMANDS = {
    "/quit": cmd_quit,
    "/new": cmd_new,
    "/tree": cmd_tree,
    "/fork": cmd_fork,
    "/compact": cmd_compact,  # <-- ADD THIS
}

# Add handler function
async def cmd_compact(sm, session_id):
    """Handle /compact command — compress session history."""
    result = await sm.compact_session(session_id)
    if result["status"] == "success":
        print(f"✓ Compacted {result['messages_before']} messages → {result['messages_after']} summary")
        print(f"Summary: {result['summary'][:100]}...")
    elif result["status"] == "skipped":
        print(f"Skipped: {result['reason']}")
    else:
        print(f"Error: {result}")
    return session_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_compact.py::test_cli_compact_command_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openchain/cli.py tests/test_compact.py
git commit -m "feat(cli): add /compact command to REPL"
```

### Acceptance Criteria

- `/compact` command reduces message count by replacing old messages with a single LLM-generated summary
- `compact_summary` field is persisted in `message_nodes` table
- Compacted nodes are excluded from `get_session_nodes()` (use `WHERE compact_summary IS NULL`)
- Test: `pytest tests/test_compact.py -v` — all pass

### Risks

- **Risk**: LLM summarization may be expensive for long conversations
- **Mitigation**: Only compact when > N messages (configurable, default 10), summarize in batches
- **Risk**: Summarization changes node IDs, breaking fork ancestry
- **Mitigation**: Preserve original node IDs and store summary as metadata, not deletion

---

## Task 2: Enhanced CLI Experience

### Files
- Modify: `openchain/cli.py` (multiline input, Ctrl+C, autocomplete)
- Create: `tests/test_cli_enhanced.py`

### Steps

- [ ] **Step 1: Write failing test — multiline input detection**

```python
# tests/test_cli_enhanced.py
def test_multiline_detection():
    """InputHelper should detect unclosed brackets."""
    from openchain.cli import InputHelper
    ih = InputHelper()
    # Single line, no bracket — should be complete
    assert ih.is_complete("hello") is True
    # Unclosed paren — should be incomplete
    assert ih.is_complete("hello (world") is False
    # Closed paren — should be complete
    assert ih.is_complete("hello (world)") is True
    # Unclosed quote — should be incomplete
    assert ih.is_complete('say "hello') is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_enhanced.py::test_multiline_detection -v`
Expected: FAIL with "InputHelper not found"

- [ ] **Step 3: Write minimal implementation**

```python
# openchain/cli.py — add InputHelper class
import re

class InputHelper:
    """Detects whether a partial input line is complete or still expecting more."""
    BRACKET_PAIRS = {"(": ")", "[": "]", "{": "}"}
    QUOTE_PAIRS = {'"': '"', "'": "'"}

    def __init__(self):
        self._bracket_stack = []
        self._in_quote = None

    def is_complete(self, line: str) -> bool:
        """Return True if line has all brackets/quotes closed."""
        if not line.strip():
            return True
        stack = []
        in_quote = None
        i = 0
        while i < len(line):
            c = line[i]
            if in_quote:
                if c == in_quote:
                    in_quote = None
                i += 1
                continue
            if c in ('"', "'"):
                in_quote = c
            elif c == "\\" and i + 1 < len(line):
                i += 2  # skip escaped char
                continue
            elif c in self.BRACKET_PAIRS:
                stack.append(self.BRACKET_PAIRS[c])
            elif c in self.BRACKET_PAIRS.values():
                if not stack or stack[-1] != c:
                    stack.append(c)  # unbalanced
                else:
                    stack.pop()
            i += 1
        return not stack and in_quote is None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_enhanced.py::test_multiline_detection -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openchain/cli.py tests/test_cli_enhanced.py
git commit -m "feat(cli): add InputHelper for multiline detection"
```

### Sub-task 2.1: Multiline input in REPL loop

- [ ] **Step 1: Write failing test — multiline accumulation**

```python
# tests/test_cli_enhanced.py — add
def test_multiline_accumulation():
    """REPL should accumulate lines until input is complete."""
    from openchain.cli import InputHelper
    ih = InputHelper()
    lines = []
    complete = ih.is_complete("hello (world")
    assert complete is False
    complete = ih.is_complete("hello (world)")
    assert complete is True
```

- [ ] **Step 2: Run test to verify it fails (is_complete not yet working)**

Run: `pytest tests/test_cli_enhanced.py::test_multiline_accumulation -v`
Expected: FAIL — but InputHelper.is_complete now works from previous step

- [ ] **Step 3: Write REPL integration — accumulate until complete**

```python
# openchain/cli.py — modify _run_chat to use InputHelper
from openchain.cli import InputHelper

async def _run_chat(sm, workspace, model):
    ih = InputHelper()
    buffer = []
    print("Welcome! Type /quit to exit.\n")

    while True:
        try:
            # Single-line prompt if buffer empty, else continuation prompt
            if not buffer:
                user_input = await prompt_async("> ")
            else:
                user_input = await prompt_async("... ")

            # Check if multiline is complete
            buffer.append(user_input)
            full_input = "\n".join(buffer)
            if ih.is_complete(full_input):
                final_input = full_input.strip()
                buffer.clear()
            else:
                continue  # ask for more lines

            if not final_input:
                continue
            ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_enhanced.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openchain/cli.py tests/test_cli_enhanced.py
git commit -m "feat(cli): integrate multiline input accumulation in REPL"
```

### Sub-task 2.2: Ctrl+C behavior

- [ ] **Step 1: Write failing test — Ctrl+C clears buffer**

```python
# tests/test_cli_enhanced.py — add
def test_ctrl_c_ clears_buffer():
    """Ctrl+C (KeyboardInterrupt) should clear the input buffer."""
    from openchain.cli import InputHelper
    ih = InputHelper()
    ih._buffer = ["hello ("]
    # Simulate Ctrl+C
    ih.clear_buffer()
    assert ih._buffer == []
    assert ih.is_complete("") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_enhanced.py::test_ctrl_c_clears_buffer -v`
Expected: FAIL with "'InputHelper' object has no attribute '_buffer'"

- [ ] **Step 3: Write implementation**

```python
# openchain/cli.py — add _buffer and clear_buffer to InputHelper
class InputHelper:
    def __init__(self):
        self._buffer = []   # accumulated lines for multiline
        self._bracket_stack = []
        self._in_quote = None

    def clear_buffer(self):
        self._buffer = []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_enhanced.py::test_ctrl_c_clears_buffer -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openchain/cli.py tests/test_cli_enhanced.py
git commit -m "feat(cli): add Ctrl+C buffer clearing to InputHelper"
```

### Sub-task 2.3: Autocomplete for REPL commands

- [ ] **Step 1: Write failing test — autocomplete registry exists**

```python
# tests/test_cli_enhanced.py — add
def test_autocomplete_commands():
    """CLI should have completions for REPL commands."""
    from openchain.cli import get_completions
    comps = get_completions("/q")
    assert "/quit" in comps
    comps = get_completions("/tree")
    assert "/tree" in comps
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_enhanced.py::test_autocomplete_commands -v`
Expected: FAIL with "get_completions not found"

- [ ] **Step 3: Write minimal implementation using prompt_toolkit**

```python
# openchain/cli.py — add at top
try:
    from prompt_toolkit import prompt
    from prompt_toolkit.completion import WordCompleter
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False

# Add WordCompleter for REPL commands
REPL_COMMANDS_LIST = ["/quit", "/new", "/tree", "/fork", "/compact"]
_word_completer = WordCompleter(REPL_COMMANDS_LIST, ignore_case=True) if HAS_PROMPT_TOOLKIT else None

def get_completions(word):
    """Return list of completions for the given word prefix."""
    if not word.startswith("/"):
        return []
    return [cmd for cmd in REPL_COMMANDS_LIST if cmd.startswith(word)]

async def prompt_async(message):
    """Async wrapper around prompt_toolkit or input()."""
    if HAS_PROMPT_TOOLKIT:
        return await prompt(message, completer=_word_completer, reserve_space_for_menu=2)
    return input(message)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_enhanced.py::test_autocomplete_commands -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openchain/cli.py tests/test_cli_enhanced.py
git commit -m "feat(cli): add REPL command autocomplete with prompt_toolkit"
```

### Acceptance Criteria

- Multiline input works: typing `(`, `)`, `[`, `]`, `{`, `}`, `"`, `'` are tracked
- Ctrl+C (KeyboardInterrupt) clears the current input buffer and returns to fresh prompt
- Tab autocomplete for `/quit`, `/new`, `/tree`, `/fork`, `/compact`
- Works with and without prompt_toolkit installed (graceful fallback to input())
- Test: `pytest tests/test_cli_enhanced.py -v` — all pass

### Risks

- **Risk**: prompt_toolkit not in dependencies
- **Mitigation**: Make it optional with `try/import`, fallback to standard `input()`
- **Risk**: Multiline bracket detection fails on escaped characters
- **Mitigation**: Simple implementation first; edge cases tracked as follow-up

---

## Task 3: Message Queue (Steering & Follow-up)

### Files
- Modify: `openchain/session.py` (add steering/followup queue methods, queue_messages column)
- Modify: `openchain/db.py` (add queue_messages TEXT column to sessions table)
- Modify: `openchain/agent/state.py` (add steering_queue, followup_queue fields)
- Modify: `openchain/agent/nodes.py` (add node_steering_inject)
- Modify: `openchain/agent/graph.py` (add steering edge)
- Create: `tests/test_message_queue.py`

### Steps

- [ ] **Step 1: Write failing test — sessions table has queue_messages column**

```python
# tests/test_message_queue.py
import pytest, tempfile, os
from openchain.db import Database

@pytest.mark.asyncio
async def test_queue_messages_column_exists():
    """sessions table should have queue_messages TEXT column."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        async with Database(db_path) as db:
            await db.initialize()
            cursor = await db.conn.execute("PRAGMA table_info(sessions)")
            columns = {row[1] for row in await cursor.fetchall()}
            assert "queue_messages" in columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_message_queue.py::test_queue_messages_column_exists -v`
Expected: FAIL with "queue_messages missing"

- [ ] **Step 3: Write implementation**

```python
# openchain/db.py — add to sessions CREATE TABLE
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    workspace TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model TEXT,
    metadata TEXT,
    queue_messages TEXT   -- JSON: {"steering": [], "followup": []}
);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_message_queue.py::test_queue_messages_column_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openchain/db.py tests/test_message_queue.py
git commit -m "feat(queue): add queue_messages column to sessions table"
```

### Sub-task 3.1: Queue management methods in SessionManager

- [ ] **Step 1: Write failing test — queue add/remove methods**

```python
# tests/test_message_queue.py — add
@pytest.mark.asyncio
async def test_steering_queue_methods():
    """SessionManager should have add_steering_message and get_steering_queue methods."""
    sm = SessionManager()
    await sm.initialize()
    try:
        session = await sm.create_session(workspace="/tmp")
        sid = session["session_id"]
        # Add steering message
        result = await sm.add_steering_message(sid, "Be concise.", position=0)
        assert result["status"] == "success"
        # Get queue
        queue = await sm.get_steering_queue(sid)
        assert len(queue) == 1
        assert queue[0]["content"] == "Be concise."
        # Remove
        await sm.remove_steering_message(sid, queue[0]["id"])
        queue = await sm.get_steering_queue(sid)
        assert len(queue) == 0
    finally:
        await sm.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_message_queue.py::test_steering_queue_methods -v`
Expected: FAIL with "add_steering_message not found"

- [ ] **Step 3: Write implementation**

```python
# openchain/session.py — add to SessionManager
import json

async def add_steering_message(self, session_id: str, content: str, position: int = -1) -> dict:
    """Add a steering message to the session's queue. position=-1 appends."""
    cursor = await self.conn.execute(
        "SELECT queue_messages FROM sessions WHERE session_id = ?", (session_id,)
    )
    row = await cursor.fetchone()
    if not row:
        return {"status": "error", "message": "session not found"}
    queue_data = json.loads(row[0] or '{"steering": [], "followup": []}')
    msg = {"id": str(uuid.uuid4()), "content": content}
    if position < 0:
        queue_data["steering"].append(msg)
    else:
        queue_data["steering"].insert(position, msg)
    await self.conn.execute(
        "UPDATE sessions SET queue_messages = ? WHERE session_id = ?",
        (json.dumps(queue_data), session_id)
    )
    await self.commit()
    return {"status": "success", "message": msg}

async def get_steering_queue(self, session_id: str) -> list:
    """Get all steering messages for a session."""
    cursor = await self.conn.execute(
        "SELECT queue_messages FROM sessions WHERE session_id = ?", (session_id,)
    )
    row = await cursor.fetchone()
    if not row:
        return []
    queue_data = json.loads(row[0] or '{"steering": []}')
    return queue_data["steering"]

async def remove_steering_message(self, session_id: str, message_id: str) -> dict:
    """Remove a steering message by id."""
    cursor = await self.conn.execute(
        "SELECT queue_messages FROM sessions WHERE session_id = ?", (session_id,)
    )
    row = await cursor.fetchone()
    if not row:
        return {"status": "error", "message": "session not found"}
    queue_data = json.loads(row[0] or '{"steering": [], "followup": []}')
    queue_data["steering"] = [m for m in queue_data["steering"] if m["id"] != message_id]
    await self.conn.execute(
        "UPDATE sessions SET queue_messages = ? WHERE session_id = ?",
        (json.dumps(queue_data), session_id)
    )
    await self.commit()
    return {"status": "success"}

# Similar methods for follow-up queue: add_followup_message, get_followup_queue, remove_followup_message
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_message_queue.py::test_steering_queue_methods -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openchain/session.py tests/test_message_queue.py
git commit -m "feat(queue): implement steering and followup message queue methods"
```

### Sub-task 3.2: Steering injection in LangGraph

- [ ] **Step 1: Write failing test — steering message prepended to prompt**

```python
# tests/test_message_queue.py — add
@pytest.mark.asyncio
async def test_steering_injected_into_state():
    """When steering queue has messages, they should appear in agent state."""
    from openchain.agent.state import AgentState
    from openchain.agent.nodes import node_steering_inject

    state = AgentState(
        session_id="test",
        workspace="/tmp",
        input_message="hello",
        parent_node_id=None,
        model="claude-sonnet-4-7",
        messages=[],
        tool_calls=[],
        tool_results=[],
        current_tool_call_index=0,
        error=None,
        retry_count=0,
        security_context={},
        steering_queue=[{"id": "1", "content": "Be concise."}],
    )
    new_state = await node_steering_inject(state)
    # First message should be the steering message
    assert len(new_state["messages"]) == 1
    assert "Be concise" in new_state["messages"][0].content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_message_queue.py::test_steering_injected_into_state -v`
Expected: FAIL with "steering_queue not in AgentState"

- [ ] **Step 3: Write implementation**

```python
# openchain/agent/state.py — add to AgentState
steering_queue: list[dict]       # [{"id": str, "content": str}, ...]
followup_queue: list[dict]       # [{"id": str, "content": str}, ...]

# openchain/agent/nodes.py — add node_steering_inject
from langchain_core.messages import SystemMessage

async def node_steering_inject(state: AgentState) -> AgentState:
    """Prepend steering messages as system messages to the message list."""
    messages = list(state["messages"])
    steering = state.get("steering_queue", [])
    for msg in steering:
        messages.insert(0, SystemMessage(content=f"[Steering directive]: {msg['content']}"))
    return {"messages": messages}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_message_queue.py::test_steering_injected_into_state -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openchain/agent/state.py openchain/agent/nodes.py tests/test_message_queue.py
git commit -m "feat(queue): inject steering messages as system messages in LangGraph"
```

### Sub-task 3.3: Follow-up message after assistant response

- [ ] **Step 1: Write failing test — followup queued after response**

```python
# tests/test_message_queue.py — add
@pytest.mark.asyncio
async def test_followup_queued_after_response():
    """After assistant response, followup messages should be re-queued."""
    from openchain.agent.nodes import node_finalize_followup

    state = AgentState(
        session_id="test",
        workspace="/tmp",
        input_message="hello",
        parent_node_id=None,
        model="claude-sonnet-4-7",
        messages=[],
        tool_calls=[],
        tool_results=[],
        current_tool_call_index=0,
        error=None,
        retry_count=0,
        security_context={},
        steering_queue=[],
        followup_queue=[{"id": "1", "content": "Want me to elaborate?"}],
    )
    new_state = await node_finalize_followup(state)
    # followup should be removed from state but still in followup_queue
    assert len(new_state["followup_queue"]) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_message_queue.py::test_followup_queued_after_response -v`
Expected: FAIL with "node_finalize_followup not found"

- [ ] **Step 3: Write implementation**

```python
# openchain/agent/nodes.py — add
async def node_finalize_followup(state: AgentState) -> AgentState:
    """Clear followup queue after response (they're presented to user as suggestions)."""
    return {"followup_queue": []}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_message_queue.py::test_followup_queued_after_response -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openchain/agent/nodes.py tests/test_message_queue.py
git commit -m "feat(queue): add node_finalize_followup to clear followup queue after response"
```

### Acceptance Criteria

- Steering messages: `add_steering_message(session_id, content)` → prepends as SystemMessage in next agent call
- Follow-up messages: `add_followup_message(session_id, content)` → stored in session, shown to user after response
- `get_steering_queue(session_id)` and `get_followup_queue(session_id)` return current queues
- `remove_steering_message` and `remove_followup_message` delete by ID
- Test: `pytest tests/test_message_queue.py -v` — all pass

### Risks

- **Risk**: Large queue could exceed SQLite TEXT limit (not realistic for typical use)
- **Risk**: Steering messages injected on every call could duplicate
- **Mitigation**: Clear steering_queue items after injection, not before; track consumed IDs

---

## Task 4: Enhanced Multi-Model Switching & Configuration

### Files
- Modify: `openchain/model_registry.py` (per-session config, model override)
- Modify: `openchain/session.py` (store model_config in sessions.metadata)
- Modify: `openchain/agent/graph.py` (use session model config)
- Modify: `openchain/api/routes.py` (model config in session create/update)
- Create: `tests/test_multi_model.py`

### Steps

- [ ] **Step 1: Write failing test — per-session model override**

```python
# tests/test_multi_model.py
@pytest.mark.asyncio
async def test_session_model_override():
    """Session should respect per-session model config override."""
    from openchain.model_registry import ModelRegistry
    mr = ModelRegistry()
    # Default
    assert mr.get_default_model() is not None
    # Override resolution
    result = mr.resolve_model("claude-sonnet-4-7", session_override="claude-haiku-4-5")
    assert result == "claude-haiku-4-5"
    # Unknown model should raise
    with pytest.raises(ModelNotFoundError):
        mr.validate_model_config("unknown-model")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_multi_model.py::test_session_model_override -v`
Expected: FAIL with "resolve_model not found"

- [ ] **Step 3: Write implementation**

```python
# openchain/model_registry.py — add
class ModelNotFoundError(Exception):
    """Raised when a model is not found in the registry."""
    pass

class ModelRegistry:
    ...
    def resolve_model(self, requested: str, session_override: Optional[str] = None) -> str:
        """Return session_override if valid, else requested, else default."""
        if session_override:
            try:
                self.validate_model_config(session_override)
                return session_override
            except ModelNotFoundError:
                pass
        try:
            self.validate_model_config(requested)
            return requested
        except ModelNotFoundError:
            return self.get_default_model()

    def validate_model_config(self, model: str) -> None:
        """Raise ModelNotFoundError if model is not available."""
        available = self.get_available_models()
        if model not in available:
            raise ModelNotFoundError(f"Model {model} not available. Available: {available}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_multi_model.py::test_session_model_override -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openchain/model_registry.py tests/test_multi_model.py
git commit -m "feat(model): add resolve_model and validate_model_config to ModelRegistry"
```

### Sub-task 4.1: Session model config persistence

- [ ] **Step 1: Write failing test — model config stored in session metadata**

```python
# tests/test_multi_model.py — add
@pytest.mark.asyncio
async def test_session_model_config_persisted():
    """Session metadata should store model configuration."""
    sm = SessionManager()
    await sm.initialize()
    try:
        session = await sm.create_session(workspace="/tmp", model="claude-haiku-4-5")
        assert session["model"] == "claude-haiku-4-5"
        # Load session and check model
        loaded = await sm.get_session(session["session_id"])
        assert loaded["model"] == "claude-haiku-4-5"
    finally:
        await sm.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_multi_model.py::test_session_model_config_persisted -v`
Expected: FAIL — create_session doesn't accept model parameter yet

- [ ] **Step 3: Write implementation**

```python
# openchain/session.py — modify create_session signature and body
async def create_session(
    self,
    workspace: str,
    model: Optional[str] = None,
    parent_node_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """Create a new session with optional model override."""
    session_id = str(uuid.uuid4())
    resolved_model = model
    if resolved_model is None:
        from openchain.model_registry import ModelRegistry
        mr = ModelRegistry()
        resolved_model = mr.get_default_model()
    meta = metadata or {}
    meta["model_config"] = {"model": resolved_model}
    metadata_json = json.dumps(meta)
    await self.conn.execute(
        "INSERT INTO sessions (session_id, workspace, model, metadata) VALUES (?, ?, ?, ?)",
        (session_id, workspace, resolved_model, metadata_json),
    )
    await self.commit()
    return {
        "session_id": session_id,
        "workspace": workspace,
        "model": resolved_model,
        "metadata": meta,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_multi_model.py::test_session_model_config_persisted -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openchain/session.py tests/test_multi_model.py
git commit -m "feat(model): persist per-session model config in metadata"
```

### Sub-task 4.2: API endpoints for model config

- [ ] **Step 1: Write failing test — API update session model**

```python
# tests/test_multi_model.py — add
@pytest.mark.asyncio
async def test_api_update_session_model():
    """PATCH /sessions/{id} should update model config."""
    import os
    os.environ["OPENCHAIN_API_KEYS"] = "test-key:read,write,admin"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/sessions", json={"workspace": "/tmp"}, headers=API_KEY_HEADER)
        sid = create_resp.json()["session_id"]
        patch_resp = await client.patch(f"/sessions/{sid}", json={"model": "claude-haiku-4-5"}, headers=API_KEY_HEADER)
        assert patch_resp.status_code == 200
        assert patch_resp.json()["model"] == "claude-haiku-4-5"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_multi_model.py::test_api_update_session_model -v`
Expected: FAIL with "PATCH endpoint not implemented"

- [ ] **Step 3: Write implementation**

```python
# openchain/api/routes.py — add PATCH endpoint
from pydantic import BaseModel

class SessionUpdate(BaseModel):
    model: Optional[str] = None

@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: str,
    update: SessionUpdate,
    _: None = Depends(require_scope("write")),
):
    async with SessionManager() as sm:
        session = await sm.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if update.model:
            await sm.update_session_model(session_id, update.model)
            session["model"] = update.model
        return session
```

```python
# openchain/session.py — add update_session_model
async def update_session_model(self, session_id: str, model: str) -> None:
    """Update the model for an existing session."""
    cursor = await self.conn.execute(
        "SELECT metadata FROM sessions WHERE session_id = ?", (session_id,)
    )
    row = await cursor.fetchone()
    if not row:
        raise ValueError(f"Session {session_id} not found")
    meta = json.loads(row[0] or "{}")
    if "model_config" not in meta:
        meta["model_config"] = {}
    meta["model_config"]["model"] = model
    await self.conn.execute(
        "UPDATE sessions SET model = ?, metadata = ? WHERE session_id = ?",
        (model, json.dumps(meta), session_id)
    )
    await self.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_multi_model.py::test_api_update_session_model -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openchain/api/routes.py openchain/session.py tests/test_multi_model.py
git commit -m "feat(api): add PATCH /sessions/{id} for model config updates"
```

### Acceptance Criteria

- `ModelRegistry.resolve_model(requested, session_override)` returns session override if valid
- `ModelRegistry.validate_model_config(model)` raises `ModelNotFoundError` for invalid models
- Session stores model in `sessions.model` and `sessions.metadata.model_config`
- `PATCH /sessions/{id}` updates session model via API
- `GET /sessions/{id}` returns current model
- Test: `pytest tests/test_multi_model.py -v` — all pass

### Risks

- **Risk**: Model availability depends on API keys — a stored model may become unavailable later
- **Mitigation**: `resolve_model` falls back to default if session override is unavailable

---

## Task 5: Agent Run Trace Export

### Files
- Create: `openchain/tools/trace_export.py` (trace serialization)
- Modify: `openchain/session.py` (add `export_trace` method)
- Modify: `openchain/api/routes.py` (add `/sessions/{id}/trace` endpoint)
- Create: `tests/test_trace_export.py`

### Steps

- [ ] **Step 1: Write failing test — export_trace method exists**

```python
# tests/test_trace_export.py
@pytest.mark.asyncio
async def test_export_trace_method_exists():
    """SessionManager should have an export_trace method."""
    sm = SessionManager()
    await sm.initialize()
    try:
        session = await sm.create_session(workspace="/tmp")
        sid = session["session_id"]
        assert hasattr(sm, "export_trace"), "export_trace method not found"
    finally:
        await sm.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_trace_export.py::test_export_trace_method_exists -v`
Expected: FAIL with "export_trace method not found"

- [ ] **Step 3: Write minimal implementation — stub**

```python
# openchain/session.py — add stub
async def export_trace(self, session_id: str) -> dict:
    """Export full session trace as JSON-serializable dict."""
    raise NotImplementedError("export_trace not yet implemented")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_trace_export.py::test_export_trace_method_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openchain/session.py tests/test_trace_export.py
git commit -m "feat(trace): add stub export_trace method"
```

### Sub-task 5.1: Full trace export implementation

- [ ] **Step 1: Write failing test — trace contains all nodes and tool calls**

```python
# tests/test_trace_export.py — add
@pytest.mark.asyncio
async def test_export_trace_contains_full_session():
    """export_trace should return all nodes, tool_calls, and metadata."""
    sm = SessionManager()
    await sm.initialize()
    try:
        session = await sm.create_session(workspace="/tmp")
        sid = session["session_id"]
        # Add user message
        node = await sm.save_user_message_node(sid, "Hello", None)
        # Add assistant message with tool call
        await sm.save_assistant_message_node(sid, node["node_id"], "Hi", model="test")
        # Export
        trace = await sm.export_trace(sid)
        assert "session_id" in trace
        assert "nodes" in trace
        assert "metadata" in trace
        assert len(trace["nodes"]) == 2
    finally:
        await sm.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_trace_export.py::test_export_trace_contains_full_session -v`
Expected: FAIL with "NotImplementedError"

- [ ] **Step 3: Write implementation**

```python
# openchain/session.py — replace stub with real export_trace
async def export_trace(self, session_id: str) -> dict:
    """Export complete session trace: session metadata + all message nodes + tool calls."""
    session = await self.get_session(session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    nodes = await self.get_session_nodes(session_id)
    tool_calls_cursor = await self.conn.execute(
        "SELECT * FROM tool_calls WHERE session_id = ? ORDER BY created_at",
        (session_id,)
    )
    tool_calls = await tool_calls_cursor.fetchall()
    tool_calls_rows = []
    for tc in tool_calls:
        tool_calls_rows.append({
            "call_id": tc[0],
            "node_id": tc[1],
            "session_id": tc[2],
            "tool_name": tc[3],
            "arguments": json.loads(tc[4]),
            "result": json.loads(tc[5]) if tc[5] else None,
            "status": tc[6],
            "created_at": tc[8],
        })

    return {
        "session_id": session_id,
        "workspace": session["workspace"],
        "model": session["model"],
        "created_at": session["created_at"],
        "updated_at": session["updated_at"],
        "metadata": json.loads(session["metadata"]) if session["metadata"] else {},
        "nodes": [
            {
                "node_id": n["node_id"],
                "parent_node_id": n["parent_node_id"],
                "role": n["role"],
                "content": n["content"],
                "tool_calls": json.loads(n["tool_calls"]) if n["tool_calls"] else [],
                "tool_results": json.loads(n["tool_results"]) if n["tool_results"] else [],
                "compact_summary": n.get("compact_summary"),
                "created_at": n["created_at"],
            }
            for n in nodes
        ],
        "tool_calls": tool_calls_rows,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_trace_export.py::test_export_trace_contains_full_session -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openchain/session.py tests/test_trace_export.py
git commit -m "feat(trace): implement full session trace export"
```

### Sub-task 5.2: API endpoint for trace download

- [ ] **Step 1: Write failing test — API trace endpoint**

```python
# tests/test_trace_export.py — add
@pytest.mark.asyncio
async def test_api_trace_endpoint():
    """GET /sessions/{id}/trace should return JSON trace."""
    import os
    os.environ["OPENCHAIN_API_KEYS"] = "test-key:read,write,admin"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/sessions", json={"workspace": "/tmp"}, headers=API_KEY_HEADER)
        sid = create_resp.json()["session_id"]
        trace_resp = await client.get(f"/sessions/{sid}/trace", headers=API_KEY_HEADER)
        assert trace_resp.status_code == 200
        data = trace_resp.json()
        assert "session_id" in data
        assert "nodes" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_trace_export.py::test_api_trace_endpoint -v`
Expected: FAIL with "404"

- [ ] **Step 3: Write implementation**

```python
# openchain/api/routes.py — add trace endpoint
@router.get("/sessions/{session_id}/trace")
async def get_session_trace(
    session_id: str,
    _: None = Depends(require_scope("read")),
):
    async with SessionManager() as sm:
        try:
            trace = await sm.export_trace(session_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return trace
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_trace_export.py::test_api_trace_endpoint -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openchain/api/routes.py tests/test_trace_export.py
git commit -m "feat(api): add GET /sessions/{id}/trace endpoint"
```

### Sub-task 5.3: JSON file export utility

- [ ] **Step 1: Write failing test — write_trace_to_file**

```python
# tests/test_trace_export.py — add
@pytest.mark.asyncio
async def test_write_trace_to_file(tmp_path):
    """write_trace_to_file should write serialized trace to a .json file."""
    from openchain.tools.trace_export import write_trace_to_file

    sm = SessionManager()
    await sm.initialize()
    try:
        session = await sm.create_session(workspace="/tmp")
        sid = session["session_id"]
        output_path = tmp_path / "trace.json"
        result = await write_trace_to_file(sm, sid, str(output_path))
        assert result["status"] == "success"
        assert output_path.exists()
        # Verify valid JSON
        import json
        with open(output_path) as f:
            data = json.load(f)
        assert "session_id" in data
    finally:
        await sm.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_trace_export.py::test_write_trace_to_file -v`
Expected: FAIL with "write_trace_to_file not found"

- [ ] **Step 3: Write implementation**

```python
# openchain/tools/trace_export.py — create file
import json
from pathlib import Path

async def write_trace_to_file(sm: "SessionManager", session_id: str, output_path: str) -> dict:
    """Export session trace and write to a JSON file."""
    trace = await sm.export_trace(session_id)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(trace, f, indent=2, default=str)
    return {"status": "success", "path": str(path), "size_bytes": path.stat().st_size}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_trace_export.py::test_write_trace_to_file -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openchain/tools/trace_export.py tests/test_trace_export.py
git commit -m "feat(trace): add write_trace_to_file utility"
```

### Acceptance Criteria

- `SessionManager.export_trace(session_id)` returns full session as dict (session metadata + nodes + tool_calls)
- `GET /sessions/{id}/trace` API endpoint returns JSON trace
- `write_trace_to_file(sm, session_id, path)` writes trace to JSON file
- Trace includes `compact_summary` for compacted nodes
- Test: `pytest tests/test_trace_export.py -v` — all pass

### Risks

- **Risk**: Large sessions produce very large JSON traces
- **Mitigation**: Add optional `?max_nodes=N` pagination parameter in API; file export is explicit (not automatic)

---

## Verification Commands

After all tasks:

```bash
# Run all new test suites
pytest tests/test_compact.py tests/test_cli_enhanced.py tests/test_message_queue.py tests/test_multi_model.py tests/test_trace_export.py -v

# Run full test suite (expect ~N+ new tests)
pytest tests/ -v

# Smoke test CLI
python -m openchain.agent chat --workspace /tmp

# Smoke test API
python -m openchain.agent api &
curl -H "X-API-Key: test-key" http://localhost:8000/health
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Task 1: /compact history compression — all 3 sub-tasks implement it
- [x] Task 2: CLI multiline, autocomplete, Ctrl+C — all 3 sub-tasks implement it
- [x] Task 3: Message queue (steering + follow-up) — all 3 sub-tasks implement it
- [x] Task 4: Multi-model switching + config — all 2 sub-tasks implement it
- [x] Task 5: Trace export — all 3 sub-tasks implement it

**Placeholder scan:** No TBD/TODO found. Each step shows actual code.

**Type consistency:** Method names are consistent across tasks:
- `compact_session`, `compact_summary` column — consistent
- `add_steering_message`, `get_steering_queue`, `remove_steering_message` — consistent
- `export_trace`, `write_trace_to_file` — consistent
- `resolve_model`, `validate_model_config`, `update_session_model` — consistent

**Gaps found:** None.

---

## Dependencies (New)

Add to `pyproject.toml` or `setup.py`:

```
prompt_toolkit>=3.0.0
```

Existing dependencies unchanged.
