# Post-MVP Roadmap

## Overview

This document outlines planned improvements and enhancements for OpenChain Agent beyond the v0.1.0 MVP release.

## Priority Levels

- **P0**: Critical - Blocks production use
- **P1**: High - Important for stability
- **P2**: Medium - Enhanced functionality
- **P3**: Low - Nice to have

---

## Phase 1: Architecture Improvements

### P0: Error Node Integration
**Issue**: LangGraph error node is currently unreachable - no routing leads to it.

**Solution**: Implement proper error routing:
- Add error detection in call_model node
- Route to handle_error on API errors or tool failures
- Implement retry logic with exponential backoff

### P0: Connection Pooling for SQLite
**Issue**: Each request creates a new Database instance and connection.

**Solution**: Implement connection pooling or lifespan events in FastAPI.

---

## Phase 2: Enhanced Security

### P0: Bash Confirmation Flow in CLI
**Issue**: Dangerous bash commands are blocked but users cannot confirm.

**Solution**:
- Implement interactive confirmation prompt in CLI
- Track user-confirmed commands in session
- Add timeout for confirmation state

### P1: Enhanced SSRF Protection
**Issue**: WebFetchTool resolves DNS but doesn't cache results.

**Solution**:
- Add DNS resolution caching
- Implement allowlist for internal services
- Block data: URLs and other dangerous schemes

### P1: Path Traversal Hardening
**Issue**: symlink protection uses realpath but doesn't handle all edge cases.

**Solution**:
- Add inode tracking to prevent symlink swapping after check
- Implement workspace snapshot on session start

---

## Phase 3: User Experience

### P1: /compact Command
**Issue**: Long conversations exhaust context windows.

**Solution**:
- Implement session compaction (similar to pi.dev)
- Preserve recent messages, summarize older ones
- Add custom compaction instructions support

### P2: CLI Auto-completion
**Issue**: No shell auto-completion for commands and paths.

**Solution**:
- Add click shell complete integration
- Path completion for file tools
- Command argument completion

### P2: Message Queue
**Issue**: Users cannot queue messages while agent is working.

**Solution**:
- Implement steering message vs follow-up message distinction
- Alt+Enter for follow-up queueing
- Message queue display

### P3: Interactive Diff for Edits
**Issue**: edit_file is a blunt replacement tool.

**Solution**:
- Add interactive diff preview
- Support for multi-file refactoring
- Undo support for edit operations

---

## Phase 4: Platform Integration

### P2: Model Switching
**Issue**: Only one model can be configured at a time.

**Solution**:
- Support per-session model selection
- Model comparison mode
- Cost tracking per model

### P3: Web UI
**Issue**: No visual interface for non-CLI users.

**Solution**:
- Simple chat web interface
- Session browser
- Settings panel

### P3: Plugin System
**Issue**: Users cannot extend with custom tools.

**Solution**:
- Plugin discovery mechanism
- Custom tool registration API
- Plugin marketplace documentation

---

## Phase 5: Performance

### P1: Response Streaming
**Issue**: Users wait for complete response before seeing output.

**Solution**:
- SSE streaming for API
- Real-time tool output streaming
- Progress indicators

### P2: Tool Caching
**Issue**: Same files read multiple times.

**Solution**:
- Content-addressed cache for file reads
- TTL-based cache invalidation
- Workspace indexing

---

## Backlog

- Integration with code editors (VS Code, JetBrains)
- Git integration enhancements
- Test generation from conversation
- Documentation auto-generation
- Multi-agent collaboration

---

## Contributing

See CONTRIBUTING.md for guidelines on implementing roadmap items.