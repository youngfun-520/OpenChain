# Post-MVP Roadmap

## Overview

This document outlines planned improvements and enhancements for OpenChain Agent beyond the v0.1.0 MVP release.

## Priority Levels

- **P0**: Critical - Blocks production use
- **P1**: High - Important for stability
- **P2**: Medium - Enhanced functionality
- **P3**: Low - Nice to have

---

## Completed

### /compact Command (v0.2.0)
- Implemented session compaction to preserve recent messages and summarize older ones
- Custom compaction instructions support added

### CLI Auto-completion (v0.2.0)
- Click shell complete integration for commands and paths
- Command argument completion implemented

### Message Queue (v0.2.0)
- Steering message vs follow-up message distinction implemented
- Alt+Enter for follow-up queueing
- Message queue display

### Model Switching (v0.2.0)
- Per-session model selection supported
- Model comparison mode
- Cost tracking per model

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

### P3: Interactive Diff for Edits
**Issue**: edit_file is a blunt replacement tool.

**Solution**:
- Add interactive diff preview
- Support for multi-file refactoring
- Undo support for edit operations

---

## Phase 4: Platform Integration

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