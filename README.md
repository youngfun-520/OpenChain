# OpenChain Agent

基于 LangGraph + SQLite 的可扩展 AI 编程助手，支持 CLI 和 REST API 两种交互模式。

## 特性

- **多轮对话**: LangGraph 单轮 invoke，多轮由外层循环调用
- **会话管理**: SQLite 持久化，消息节点树结构，支持分支(fork)
- **双模式**:
  - CLI 交互模式 (`python -m openchain.agent chat`)
  - FastAPI REST API (`python -m openchain.agent api`)
- **工具系统**:
  - 文件操作: read_file, write_file, edit_file, list_dir, grep
  - Bash 执行: bash (危险命令拦截)
  - 网络搜索: web_search, web_fetch (SSRF 防护)
- **安全策略**:
  - Workspace 路径限制 (symlink 防穿越)
  - 危险命令黑名单 (fork bomb, dd, rm -rf 等)
  - API 模式 bash 默认禁用
  - 完整审计日志 (tool_calls 表)

## 安装

```bash
pip install -e .
```

## 配置

创建 `.env` 文件:

```bash
# LLM Provider Keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
DEEPSEEK_API_KEY=sk-...

# 配置
OPENCHAIN_DATA_DIR=~/.openchain/data
OPENCHAIN_WORKSPACE_ROOT=.
OPENCHAIN_DEFAULT_MODEL=claude-sonnet-4-7
OPENCHAIN_API_ENABLE_BASH=false
OPENCHAIN_BASH_TIMEOUT=30

# API Keys — 格式: key1:scope1,scope2|key2
OPENCHAIN_API_KEYS=key1:read,write|key2:read

# Sandbox 安全加固
OPENCHAIN_READONLY_WORKSPACE=1   # 禁用写文件操作
OPENCHAIN_SANDBOX_MODE=1         # 限制 bash 可用命令
```

## 使用

### CLI 模式

```bash
python -m openchain.agent chat --workspace /path/to/project
```

命令:
- `/new` - 新建会话
- `/tree` - 查看会话树
- `/fork <node_id>` - 从指定节点分叉
- `/compact` - 压缩会话历史（LLM 摘要）
- `/quit` - 退出

**多行输入:** 输入未闭合的括号、引号时，自动继续输入直到闭合。
**Ctrl+C:** 清空当前输入 buffer，不退出会话。

### API 模式

```bash
python -m openchain.agent api
```

端点:
- `GET /health` - 健康检查（无需认证）
- `POST /sessions` - 创建会话
- `GET /sessions/{id}` - 获取会话
- `PATCH /sessions/{id}` - 更新会话（如切换模型）
- `DELETE /sessions/{id}` - 删除会话
- `GET /sessions/{id}/tree` - 获取会话树
- `GET /sessions/{id}/trace` - 导出会话完整轨迹（nodes + tool_calls + audit_logs）
- `POST /sessions/{id}/fork` - 分叉会话
- `POST /chat` - 发送消息

所有端点（除 `/health`）需要 `X-API-Key` 头：

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/sessions
```

环境变量配置：
```bash
# API Keys — 格式: key1:scope1,scope2|key2:scope1|key3
# scope 可选值: read, write, admin
# admin 拥有所有权限
OPENCHAIN_API_KEYS=key1:read,write|key2:read|admin-key:read,write,admin
```

### API Scopes

| Scope | 权限 |
|-------|------|
| `read` | 读取会话列表、获取会话、查看会话树 |
| `write` | 创建/删除会话、发送消息、分叉 |
| `admin` | 所有权限，包括 write |

### API 审计日志

所有 API 请求（除 `/health`）都会记录到 `audit_logs` 表：

```bash
# 请求头
curl -H "X-API-Key: your-key" http://localhost:8000/sessions
```

日志包含: key_label, endpoint, method, status_code, client_ip, timestamp, request_id

## 测试

```bash
pytest tests/ -v
```

## 项目结构

```
openchain/
├── agent.py          # CLI/API 入口
├── cli.py            # CLI 实现
├── db.py             # SQLite 数据库层
├── session.py        # 会话管理
├── model_registry.py # 多模型管理
├── security.py       # 安全检查
├── api/
│   └── routes.py     # FastAPI 路由
├── agent/
│   ├── state.py      # LangGraph AgentState
│   ├── nodes.py      # 节点实现
│   └── graph.py      # 工作流定义
└── tools/
    ├── base.py       # 工具基类
    ├── file_tools.py # 文件操作
    ├── bash_tool.py  # Bash 执行
    └── web_tools.py  # 网络工具
```

## 安全说明

- 文件操作限制在 workspace 内
- 危险 bash 命令自动拦截
- API 模式默认禁用 bash
- 所有工具调用记录审计日志

### Sandbox 安全加固

**敏感文件保护:** 以下文件类型自动拦截读写操作：
- 凭据文件: `.env`, `id_rsa`, `secrets.json`, `.aws/credentials`, `.gcp/*.json`, `.docker/config.json`
- 配置凭据: `.git/config`, `.npmrc`, `.pypirc`, `.netrc`, `.pgpass`, `.my.cnf`, `config.py`

**只读模式:** `OPENCHAIN_READONLY_WORKSPACE=1` 禁用所有写文件操作

**受限 bash:** `OPENCHAIN_SANDBOX_MODE=1` 限制可用命令，阻止：
- 网络工具: `curl`, `wget`, `nc`, `telnet`, `ssh`
- 容器/集群: `docker`, `kubectl`, `terraform`, `ansible`
- 脚本解释器: `python`, `node`, `ruby`, `perl`, `bash`, `sh`
- 系统修改: `chmod`, `chown`, `setfacl`

## 后续事项

- error node 路由优化
- /compact 会话压缩 ✅
- CLI 自动补全增强 ✅
- 消息队列功能 ✅

## License

MIT