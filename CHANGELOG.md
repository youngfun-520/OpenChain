# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-05-29

### Features

- **/compact History Compression**
  - `compact_session()` compresses session history via LLM summarization
  - Original message nodes preserved with `compact_summary` field (not deleted)
  - New CLI command: `/compact`

- **Enhanced CLI Experience**
  - Multiline input detection (brackets `()`, `[]`, `{}`, quotes `"`, `'`)
  - Ctrl+C clears input buffer without exiting REPL
  - REPL command autocomplete via `get_completions()` function

- **Message Queue**
  - `steering_queue`: prepend directives to next agent call (consumed after injection)
  - `followup_queue`: persist suggestions shown to user after response
  - Stored in `sessions.queue_messages` JSON column
  - `node_steering_inject` and `node_finalize_followup` wired into LangGraph workflow

- **Multi-Model Switching**
  - `ModelRegistry.resolve_model(requested, session_override)` for per-session override
  - `ModelRegistry.validate_model_config(model)` raises `ModelNotFoundError` for invalid models
  - `PATCH /sessions/{id}` endpoint to update session model
  - `fork_session` preserves parent model

- **Trace Export**
  - `export_trace(session_id)`: session metadata + all nodes + tool_calls + audit_logs
  - `GET /sessions/{id}/trace` API endpoint
  - `write_trace_to_file(sm, session_id, path)` utility

### Tests

- 84 tests passed (up from 63 in v0.1.2)

## [0.1.2] - 2026-05-29

### Security

- **Enhanced API Permission Model**
  - Multi-key support with scopes: `read`, `write`, `admin`
  - Keys via `OPENCHAIN_API_KEYS` env var (format: `key1:read,write|key2:read`)
  - Request audit logging to `audit_logs` table (key_label, endpoint, method, status_code, client_ip, timestamp, request_id)

- **Enhanced Sandbox**
  - Sensitive file detection: blocks `.env`, `id_rsa`, `secrets.json`, `.aws/credentials`, `.gcp/*.json`, `.docker/config.json`, `.git/config`, `.npmrc`, `.pypirc`, `.netrc`, `.pgpass`, `.my.cnf`, `config.py`
  - Workspace read-only mode: set `OPENCHAIN_READONLY_WORKSPACE=1`
  - Restricted bash profile: set `OPENCHAIN_SANDBOX_MODE=1` to block curl, wget, nc, ssh, docker, kubectl, python, etc.

### Reliability

- **aiosqlite Event Loop Cleanup**
  - Added `cleanup_db_connections` pytest fixture
  - Robust `Database.close()` with exception suppression
  - Reduced `RuntimeError: Event loop is closed` warnings in test teardown

### Testing

- **Concurrency / Stress Tests**
  - Concurrent session creation (10 parallel creates)
  - Concurrent message saves to same session
  - Concurrent tool call audit logging
  - Concurrent audit log writes
  - Parallel API endpoint tests via ThreadPoolExecutor

### Tests

- 63 tests passed (up from 42 in v0.1.1)

## [0.1.1] - 2026-05-29

### Fixed

- **Error Node Integration**
  - `handle_error` node is now reachable in LangGraph
  - `route_after_model` checks `error` state first before routing by `tool_calls`
  - LLM failures, tool execution failures, and DB errors all set `state["error"]` to trigger error routing
  - Retry logic with max 3 attempts and "Max retries exceeded" final state

- **Sandbox Hardening**
  - `BashTool` now properly `await proc.wait()` after `proc.kill()` to prevent zombie processes
  - `GrepTool` replaced bare `except: pass` with explicit `PermissionError` and `Exception` handling

### Added

- **API Authentication**
  - `X-API-Key` header authentication on all FastAPI endpoints except `/health`
  - Keys configured via `OPENCHAIN_API_KEYS` environment variable (comma-separated)
  - `openchain.api.auth` module with `verify_api_key` dependency

- **SQLite Connection Lifecycle**
  - Async context managers (`__aenter__`/`__aexit__`) on `Database` and `SessionManager`
  - Guaranteed connection cleanup via `async with` pattern
  - Routes updated to use `async with SessionManager() as sm:`
  - No pooling needed for SQLite — explicit lifecycle management instead

### Changed

- Updated existing API tests to include `X-API-Key` header

### Tests

- 42 tests passed (up from 30 in v0.1.0)

## [0.1.0] - 2026-05-29

### Added

- **LangGraph Agent Architecture**
  - Single-turn invoke pattern with multi-turn handled by CLI/API outer loop
  - State machine workflow with nodes: receive_input, load_session_context, call_model, execute_tools, save_message_node, handle_error, final_response
  - Conditional routing based on tool_calls presence

- **Session Management**
  - SQLite persistence with message node tree structure
  - Support for session branching via /fork command
  - Ancestor chain traversal for fork operation
  - Three core tables: sessions, message_nodes, tool_calls

- **CLI Mode**
  - Interactive chat with /new, /tree, /fork, /quit commands
  - Session persistence and recovery
  - Workspace-scoped file operations

- **FastAPI Mode**
  - REST API endpoints: /health, /sessions, /sessions/{id}, /sessions/{id}/tree, /sessions/{id}/fork, /chat
  - Session management via API
  - Chat interface with single-turn invoke

- **Tool System**
  - File tools: read_file, write_file, edit_file, list_dir, grep
  - Bash tool with security checks
  - Web tools: web_search, web_fetch
  - ToolRegistry singleton for tool management

- **Security**
  - Workspace path restriction with symlink traversal protection
  - Dangerous command detection (fork bomb, dd, rm -rf, etc.)
  - API mode bash disabled by default
  - WebFetch SSRF protection (blocks localhost, internal IPs)
  - Audit logging to tool_calls table

- **Model Registry**
  - Multi-provider support: Anthropic, OpenAI, DeepSeek
  - Dynamic model discovery based on API keys
  - Default model resolution from environment

### Known Issues

- /compact feature not yet implemented (session compression for long conversations)
- CLI auto-completion not yet implemented
- Message queue feature not yet implemented

### Dependencies

- Python 3.11+
- langchain>=0.3.0
- langgraph>=0.2.0
- langchain-anthropic
- langchain-openai
- langchain-deepseek
- fastapi>=0.115.0
- aiosqlite>=0.20.0
- click>=8.0.0
- python-dotenv>=1.0.0