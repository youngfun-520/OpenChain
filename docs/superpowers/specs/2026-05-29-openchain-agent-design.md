# OpenChain Agent 设计文档

**日期**: 2026-05-29
**主题**: 基于 LangGraph 的全能助手智能体
**版本**: 2.0（修订版）

---

## 1. 概述

构建一个基于 LangGraph/LangChain 的可扩展智能体，支持 CLI 和 Web API 两种交互模式，核心能力包括文件操作、bash 命令执行、网络搜索，支持多会话管理和基于消息节点树的树形分支结构。

---

## 2. 架构

### 2.1 技术栈

- **语言**: Python 3.11+
- **框架**: LangChain + LangGraph
- **LLM 提供者**: 多 provider 支持（Anthropic、OpenAI、DeepSeek 等）
- **CLI**: 交互式命令行界面（click 或 built-in）
- **API**: FastAPI
- **存储**: SQLite（JSONL 仅作为导出/备份格式）

### 2.2 核心组件架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent Entry                           │
│                      (agent.py)                            │
└─────────────────┬───────────────────────────────────────────┘
                  │
        ┌────────┴────────┐
        ▼                 ▼
┌───────────────┐    ┌─────────────┐
│   CLI Mode   │    │  FastAPI   │
└───────────────┘    └─────────────┘
        │                 │
        └────────┬────────┘
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                 Session Manager                            │
│        （SQLite 持久化、消息节点树、分支）                   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  LangGraph Agent                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ receive_input → load_session_context → call_model     │  │
│  │ route_after_model                                     │  │
│  │   ├→ execute_tools → save_message_node → receive_input│  │
│  │   └→ final_response (save_message_node → receive_input)│  │
│  │ handle_error → save_message_node → receive_input      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Tools Module                            │
│  read / write / edit / bash / grep / web_search            │
│  （安全策略：workspace 限制、bash 确认、审计日志）           │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 模块职责

| 模块 | 文件 | 职责 |
|------|------|------|
| 入口 | `agent.py` | CLI 和 API 启动入口，模式分发 |
| 工具 | `tools.py` | 所有工具函数定义（安全检查） |
| 会话 | `session.py` | SQLite 会话管理、节点树操作 |
| Graph | `agent/graph.py` | LangGraph 状态机和工作流 |
| 数据库 | `db.py` | SQLite 连接、Schema 定义 |
| API | `api.py` | FastAPI 路由和服务 |
| 安全 | `security.py` | 危险命令检测、workspace 限制 |

---

## 3. 数据模型

### 3.1 核心概念

- **session_id**: 一次对话会话的唯一标识
- **node_id**: 会话中每条消息（节点）的唯一标识
- **parent_node_id**: 父节点的 node_id（用于构建树形结构）
- **message**: 消息内容（user/assistant/system/tool 类型）
- **树形分支**: 通过 parent_node_id 关系组织成有向无环图（DAG）

### 3.2 数据库 Schema（SQLite）

```sql
-- sessions 表：会话元数据
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    workspace TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model TEXT,
    metadata TEXT  -- JSON 存储额外信息
);

-- message_nodes 表：消息节点树
CREATE TABLE message_nodes (
    node_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    parent_node_id TEXT,  -- NULL 表示根节点
    role TEXT NOT NULL,   -- user / assistant / system / tool
    content TEXT NOT NULL,
    tool_calls TEXT,      -- JSON 存储工具调用列表
    tool_results TEXT,    -- JSON 存储工具返回结果
    model TEXT,           -- 使用的模型
    token_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (parent_node_id) REFERENCES message_nodes(node_id)
);

-- tool_calls 表：审计日志
CREATE TABLE tool_calls (
    call_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    arguments TEXT NOT NULL,  -- JSON
    result TEXT,              -- JSON
    status TEXT NOT NULL,     -- success / failure / pending
    security_verified BOOLEAN DEFAULT FALSE,
    user_confirmed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (node_id) REFERENCES message_nodes(node_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- 索引
CREATE INDEX idx_nodes_session ON message_nodes(session_id);
CREATE INDEX idx_nodes_parent ON message_nodes(parent_node_id);
CREATE INDEX idx_tool_calls_session ON tool_calls(session_id);
CREATE INDEX idx_tool_calls_node ON tool_calls(node_id);
```

### 3.3 会话文件位置

- SQLite: `~/.openchain/data/openchain.db`
- JSONL 导出: `~/.openchain/exports/<session_id>.jsonl`

---

## 4. LangGraph 工作流详解

### 4.1 AgentState 定义

```python
class AgentState(TypedDict):
    # 会话上下文
    session_id: str
    workspace: str

    # 当前输入
    input_message: str
    parent_node_id: str | None  # 用于 /fork 后从特定节点继续

    # 模型相关
    model: str
    messages: list[BaseMessage]  # LangChain 消息历史

    # 执行状态
    tool_calls: list[dict]       # 待执行的工具调用
    tool_results: list[dict]    # 工具执行结果
    current_tool_call_index: int # 当前执行的工具索引

    # 错误处理
    error: str | None
    retry_count: int

    # 安全
    security_context: dict       # workspace 路径、危险命令确认状态等
```

### 4.2 节点定义

| 节点 | 函数 | 职责 |
|------|------|------|
| `receive_input` | `node_receive_input` | 接收用户输入，构建 user message |
| `load_session_context` | `node_load_session_context` | 从 SQLite 加载会话历史，构建 messages |
| `call_model` | `node_call_model` | 调用 LLM，返回 tool_calls 或 final_response |
| `route_after_model` | `route_after_model` | 条件路由：tool_calls → execute_tools / 无工具 → final_response |
| `execute_tools` | `node_execute_tools` | 顺序执行工具调用，收集结果 |
| `save_message_node` | `node_save_message_node` | 将 assistant 消息保存到 message_nodes 表 |
| `handle_error` | `node_handle_error` | 错误处理，决定重试或终止 |
| `final_response` | `node_final_response` | 输出最终响应给用户 |

### 4.3 路由逻辑

```python
def route_after_model(state: AgentState) -> str:
    """路由决策"""
    if state.get("tool_calls") and len(state["tool_calls"]) > 0:
        return "execute_tools"
    else:
        return "final_response"

def should_retry(state: AgentState) -> bool:
    """错误重试决策"""
    return state.get("retry_count", 0) < 3 and state.get("error") is not None
```

### 4.4 工作流图示

```
receive_input
      │
      ▼
load_session_context
      │
      ▼
call_model ──────────────────┐
      │                       │
      ▼                       │
route_after_model            │
      │                       │
      ├── [有 tool_calls] ──→ execute_tools ──→ save_message_node
      │                              │
      │                              ▼
      │                         load_session_context (循环)
      │                              │
      └── [无 tool_calls] ──→ final_response
                                    │
                                    ▼
                              save_message_node
                                    │
                                    ▼
                              receive_input (等待下一轮)
```

---

## 5. 工具定义与安全策略

### 5.1 工具列表

#### 文件操作工具

| 工具 | 功能 | 参数 | 安全限制 |
|------|------|------|----------|
| `read_file` | 读取文件内容 | `path: str` | workspace 内 |
| `write_file` | 写入文件 | `path: str, content: str` | workspace 内 |
| `edit_file` | 编辑文件 | `path: str, old: str, new: str` | workspace 内 |
| `list_dir` | 列出目录 | `path: str` | workspace 内 |
| `find_file` | 搜索文件 | `pattern: str, path: str` | workspace 内 |
| `grep` | 文本搜索 | `pattern: str, path: str` | workspace 内 |

#### Bash 工具

| 工具 | 功能 | 参数 | 安全限制 |
|------|------|------|----------|
| `bash` | 执行 shell 命令 | `command: str, timeout: int` | 高危命令需确认 |

#### 网络工具

| 工具 | 功能 | 参数 |
|------|------|------|
| `web_search` | 搜索网络 | `query: str, num_results: int` |
| `web_fetch` | 获取网页内容 | `url: str` |

### 5.2 安全策略

#### Workspace 限制
- 文件操作（read/write/edit/list_dir/find_file/grep）仅限 `workspace_root` 目录
- 工具函数入口检查路径，非法路径返回 `SecurityError`
- workspace_root 在会话创建时指定或默认当前目录

#### Bash 安全检查
- 危险命令黑名单：`rm -rf /`, `dd`, `:(){:|:&};:`, `mkfs`, `fdisk` 等
- 疑似危险模式检测：命令包含 `sudo` + `rm`, 正则表达式注入等
- CLI 模式：默认启用，危险命令提示 `Are you sure? [y/N]`
- API 模式：**默认禁用 bash**，需显式设置 `enable_bash: true`

#### 审计日志
- 所有工具调用必须记录到 `tool_calls` 表
- 记录：call_id, node_id, session_id, tool_name, arguments, result, status
- 安全相关字段：security_verified, user_confirmed

### 5.3 安全检查流程

```
工具调用请求
      │
      ▼
检查路径是否在 workspace 内 ──→ 越界 → 返回 SecurityError
      │ (文件操作)
      ▼
检查是否是危险 bash 命令 ──→ 危险 → 等待用户确认 (CLI) / 返回 SecurityError (API)
      │                       │
      ▼                       ▼
记录到 tool_calls 表      用户拒绝 → 返回 SecurityError
      │
      ▼
执行工具
      │
      ▼
更新 tool_calls 表 (result, status)
```

---

## 6. CLI 设计

### 6.1 命令

```bash
# 启动 CLI
python agent.py [--workspace <path>]

# 交互命令
/new              # 新会话
/resume <id>      # 恢复会话
/tree [session]   # 查看会话树（可选指定 session）
/fork <node_id>   # 从指定节点分叉
/model <name>     # 切换模型
/models           # 列出可用模型
/settings         # 打开设置
/compact [prompt]  # 压缩历史（可选自定义指令）
/export [path]    # 导出会话为 JSONL
/quit             # 退出
```

### 6.2 交互功能

- 文件路径自动补全（基于 workspace）
- 多行输入（Shift+Enter）
- Ctrl+C 中断当前执行
- Ctrl+C 两次：取消排队消息
- 消息队列：Enter 排队 steering message，Alt+Enter 排队 follow-up
- 危险命令确认提示

---

## 7. API 设计

### 7.1 端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/sessions` | 列出会话列表 |
| POST | `/sessions` | 创建新会话 |
| GET | `/sessions/{session_id}` | 获取会话信息 |
| DELETE | `/sessions/{session_id}` | 删除会话 |
| GET | `/sessions/{session_id}/tree` | 获取会话树结构 |
| POST | `/sessions/{session_id}/fork` | 从指定节点分叉（body: `node_id`） |
| POST | `/chat` | 发送消息 |

### 7.2 请求/响应格式

```json
// POST /sessions
// 请求
{
  "workspace": "/path/to/project",
  "model": "claude-sonnet-4-7"
}
// 响应
{
  "session_id": "abc123",
  "workspace": "/path/to/project",
  "model": "claude-sonnet-4-7",
  "created_at": "2026-05-29T10:00:00Z"
}

// POST /chat
// 请求
{
  "message": "帮我写一个 hello world",
  "session_id": "abc123",
  "parent_node_id": "node_456"  // 可选，指定从某节点继续（用于 /fork 后）
}
// 响应
{
  "session_id": "abc123",
  "node_id": "node_789",
  "response": "已创建 hello world...",
  "tool_calls": [
    {
      "tool": "write_file",
      "args": {"path": "hello.py", "content": "print('hello world')"},
      "result": {"success": true}
    }
  ],
  "model": "claude-sonnet-4-7"
}

// GET /sessions/{session_id}/tree
// 响应
{
  "session_id": "abc123",
  "nodes": [
    {"node_id": "node_1", "parent_node_id": null, "role": "user", "content": "..."},
    {"node_id": "node_2", "parent_node_id": "node_1", "role": "assistant", "content": "..."},
    {"node_id": "node_3", "parent_node_id": "node_2", "role": "user", "content": "..."}
  ]
}

// POST /sessions/{session_id}/fork
// 请求
{
  "node_id": "node_2"
}
// 响应
{
  "session_id": "abc124",  // 新会话 ID
  "forked_from_node_id": "node_2",
  "parent_node_id": "node_2"
}
```

### 7.3 API 安全配置

```json
// API 模式默认设置
{
  "enable_bash": false,      // 默认禁用 bash
  "workspace_restrict": true, // 强制 workspace 限制
  "dangerous_commands_blocked": true
}
```

---

## 8. 配置

### 8.1 环境变量（.env）

```bash
# LLM Provider Keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
DEEPSEEK_API_KEY=...

# 配置
OPENCHAIN_DATA_DIR=~/.openchain/data
OPENCHAIN_WORKSPACE_ROOT=/path/to/default/workspace
OPENCHAIN_DEFAULT_MODEL=claude-sonnet-4-7
OPENCHAIN_API_ENABLE_BASH=false  # API 默认禁用 bash
OPENCHAIN_BASH_TIMEOUT=30
```

### 8.2 多模型支持

通过 `ModelRegistry` 动态管理，支持切换。

---

## 9. 错误处理

- **工具执行失败**: 返回错误信息到 LLM，Agent 决定重试或绕过
- **LLM 调用失败**: 指数退避重试（最多 3 次）
- **会话存储失败**: 写入临时文件，定期恢复
- **安全拦截**: 返回 `SecurityError`，不执行危险操作

---

## 10. 实施计划（分阶段）

### Phase 1: 核心框架（MVP）

**目标**: 验证 LangGraph 状态机 + SQLite 存储 + CLI 基本功能

**交付物**:
- 项目目录结构初始化
- SQLite 数据库初始化（sessions, message_nodes, tool_calls 表）
- LangGraph Agent 状态机和工作流（mock tools）
- CLI 基本命令（/new, /resume, /tree, /fork, /quit）
- 会话持久化（创建/恢复/分支）

**验收标准**:
- `python agent.py` 可启动 CLI
- `/new` 创建新会话
- `/tree` 显示消息节点树
- `/fork <node_id>` 从指定节点分叉

### Phase 2: 真实工具 + 安全策略

**目标**: 实现文件操作、bash、网络工具，完整安全策略

**交付物**:
- `tools.py`: read/write/edit/bash/grep/web_search 工具
- `security.py`: workspace 限制、危险命令检测
- 工具审计日志完整记录
- CLI 危险命令确认交互
- API bash 禁用配置

**验收标准**:
- 文件操作限制在 workspace 内
- 危险 bash 命令触发确认
- 所有工具调用记录到 tool_calls 表

### Phase 3: FastAPI

**目标**: REST API 支持

**交付物**:
- `api.py`: FastAPI 服务
- API 端点实现（见第 7 节）
- API 模式默认禁用 bash
- JSONL 导出功能

**验收标准**:
- API 可启动：`python agent.py --api`
- `POST /chat` 可正常对话
- `GET /sessions/{id}/tree` 返回正确树结构

### Phase 4: 增强功能

**目标**: 生产级可用性

**交付物**:
- 会话压缩（/compact）
- 多模型动态切换
- CLI 自动补全增强
- 消息队列功能
- 其他优化

---

## 11. 目录结构

```
/home/yangfan/workspace/OpenChain/
├── agent.py              # CLI 和 API 入口
├── tools.py              # 工具函数定义
├── security.py           # 安全检查
├── session.py            # 会话管理
├── db.py                 # SQLite 连接和 Schema
├── model_registry.py     # 多模型管理
├── api.py                # FastAPI 应用
├── agent/
│   ├── __init__.py
│   └── graph.py          # LangGraph 定义
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-05-29-openchain-agent-design.md
├── tests/                # 测试
├── .env                  # 环境变量（不提交）
└── requirements.txt
```

---

**状态**: 设计已更新，待用户确认后进入 implementation planning（writing-plans）