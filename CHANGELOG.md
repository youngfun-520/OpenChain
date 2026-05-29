# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

- error node in LangGraph is unreachable (subsequent architecture improvement)
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