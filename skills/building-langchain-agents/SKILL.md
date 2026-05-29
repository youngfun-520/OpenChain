---
name: building-langchain-agents
description: Building intelligent agents with LangChain Python. Use when creating AI agents, configuring tools, implementing ReAct patterns, or designing multi-agent workflows with LangGraph.
version: 1.1.0
platforms:
  - claude
  - markdown
tags:
  - langchain
  - agents
  - llm
  - react
  - langgraph
  - tool-use
---

# Building LangChain Agents

Building intelligent agents with LangChain Python. Covers agent architecture, tool integration, ReAct patterns, memory management, and LangGraph workflows.

## When to Use This Skill

Use this skill when you need to:

- **Create agents** with `create_agent`, `create_react_agent`, `create_structured_chat_agent`
- **Configure tools** using `@tool` decorator, `StructuredTool`, or `Tool`
- **Implement ReAct loops** with `AgentExecutor` and `plan()` → `execute` → `observe` cycle
- **Build multi-agent workflows** with LangGraph's `create_react_agent`, `ToolNode`, `interrupt`
- **Manage conversation memory** with `BaseChatMessageHistory`, `ConversationBufferMemory`
- **Debug agent execution** with callbacks and `verbose` mode
- **Persist agent state** using LangGraph checkpointer

**Trigger phrases**: "create an agent", "build an agent", "add tool to agent", "ReAct agent", "agent executor", "multi-agent workflow", "LangGraph agent", "langchain agent"

## Quick Reference

### Agent Creation (Modern API)

```python
from langchain.agents import create_agent

@tool
def search(query: str) -> str:
    """Search the web for information"""
    return f"Results for: {query}"

agent = create_agent(
    model="openai:gpt-4",
    tools=[search],
    system_prompt="You are a helpful assistant"
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "What's the weather?"}]}
)
```

### Tool Definition

```python
from langchain_core.tools import tool, StructuredTool

@tool
def calculate(operation: str, a: float, b: float) -> float:
    """Perform mathematical operation"""
    ops = {"add": lambda x,y: x+y, ...}
    return ops[operation](a, b)
```

### LangGraph Agent

```python
from langgraph.prebuilt import create_react_agent

app = create_react_agent(model, tools)
result = app.invoke({"messages": [{"role": "user", "content": "..."}]})
```

### Memory Setup

```python
from langchain.memory import ConversationBufferMemory
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
```

## Code Examples

### 1. Basic Agent (Modern create_agent API)

```python
from langchain.agents import create_agent
from langchain_core.tools import tool

@tool
def get_weather(city: str) -> str:
    """Get weather for a city"""
    return f"Weather in {city}: sunny, 72°F"

@tool
def search_wikipedia(query: str) -> str:
    """Search Wikipedia"""
    return f"Wiki results for '{query}'"

tools = [get_weather, search_wikipedia]

agent = create_agent(
    model="openai:gpt-4",
    tools=tools,
    system_prompt="You are a helpful assistant with access to tools."
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "What's the weather in Tokyo?"}]}
)
print(result["messages"][-1].content_blocks)
```

### 2. ReAct Agent with AgentExecutor

```python
from langchain.agents import create_react_agent, AgentExecutor
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4", temperature=0)

@tool
def web_search(query: str) -> str:
    """Search the internet for current information"""
    return f"Search results for: {query}"

@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression"""
    return str(eval(expression))

tools = [web_search, calculator]

agent = create_react_agent(llm, tools)
executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    max_iterations=10
)

result = executor.invoke({"input": "What is 2 + 2? Search the web for confirmation."})
```

### 3. Structured Chat Agent

```python
from langchain.agents import create_structured_chat_agent
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

class SearchResult(BaseModel):
    url: str
    title: str
    snippet: str

class CalculatorInput(BaseModel):
    operation: str  # add, subtract, multiply, divide
    a: float
    b: float

@tool
def search(query: str) -> list[SearchResult]:
    """Search the web"""
    return [{"url": "...", "title": "...", "snippet": "..."}]

@tool
def calculate(operation: str, a: float, b: float) -> float:
    """Perform calculation"""
    ops = {"add": lambda x,y: x+y, "subtract": lambda x,y: x-y,
           "multiply": lambda x,y: x*y, "divide": lambda x,y: x/y if b != 0 else "error"}
    return ops[operation](a, b)

tools = [search, calculate]

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant with access to tools."),
    ("human", "{input}"),
])

agent = create_structured_chat_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
```

### 4. Agent with Conversation Memory

```python
from langchain.agents import create_react_agent, AgentExecutor
from langchain.memory import ConversationBufferMemory

memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True,
    output_key="output",
    input_key="input"
)

agent = create_react_agent(llm, tools)
executor = AgentExecutor(
    agent=agent,
    tools=tools,
    memory=memory,
    verbose=True
)

# Multi-turn conversation
result = executor.invoke({"input": "My name is Alice"})
result = executor.invoke({"input": "What's my name?"})  # Remembers "Alice"
```

### 5. LangGraph ReAct Agent with Interrupt

```python
from langgraph.prebuilt import create_react_agent
from langgraph.types import interrupt
from langchain_anthropic import ChatAnthropic

model = ChatAnthropic(model="claude-3-7-sonnet-latest")

@tool
def execute_code(code: str) -> str:
    """Execute Python code safely"""
    return "Code executed successfully"

@tool
def read_file(path: str) -> str:
    """Read file contents"""
    with open(path) as f:
        return f.read()

tools = [execute_code, read_file]
app = create_react_agent(model, tools)

# Invoke with interrupt for human approval
result = app.invoke(
    {"messages": [{"role": "user", "content": "Run this code: print('hello')"}]},
    config={"interrupt": ["execute_code"]}
)
```

### 6. Custom Callback Handler

```python
from langchain_core.callbacks import BaseCallbackHandler

class DebugHandler(BaseCallbackHandler):
    def on_llm_new_token(self, token: str, **kwargs) -> None:
        print(f"[LLM] {token}", end="", flush=True)

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs) -> None:
        print(f"\n[TOOL] Starting: {serialized.get('name', 'unknown')}")

    def on_tool_end(self, output: str, **kwargs) -> None:
        print(f"[TOOL] Done: {output[:100]}...")

    def on_agent_action(self, action: dict, **kwargs) -> None:
        print(f"\n[AGENT] Action: {action.get('tool', 'unknown')}")

handler = DebugHandler()
executor = AgentExecutor(agent=agent, tools=tools, callbacks=[handler], verbose=False)
```

### 7. Async Agent Execution

```python
import asyncio
from langchain.agents import AgentExecutor

async def run_agent_async():
    executor = AgentExecutor(agent=agent, tools=tools)
    result = await executor.arun("What is 2 + 2?")
    return result

result = asyncio.run(run_agent_async())
```

## Architecture

### Agent Type Hierarchy

```
BaseSingleActionAgent
├── Agent (abstract)
│   ├── ReActDocstoreAgent
│   ├── ConversationalAgent
│   └── XMLAgent
└── RunnableAgent

BaseMultiActionAgent
└── Agent (multi-action variants)
```

### AgentExecutor Execution Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     AgentExecutor                           │
│                                                             │
│  ┌─────────┐    ┌─────────────┐    ┌────────────────────┐  │
│  │  Plan   │───▶│   Execute   │───▶│      Observe       │  │
│  │ agent.  │    │ executor.   │    │  collect result    │  │
│  │ plan()  │    │ run(tool)   │    │                    │  │
│  └─────────┘    └─────────────┘    └─────────┬──────────┘  │
│       │                                      │             │
│       │         ┌────────────────────────────┘             │
│       │         ▼                                          │
│       │    ┌─────────────┐                                  │
│       └───▶│  Done?      │◀──────────────┐                  │
│            │ AgentFinish │               │                  │
│            └─────────────┘               │                  │
│                              loop until done                │
└─────────────────────────────────────────────────────────────┘
```

### LangGraph Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      LangGraph                               │
│                                                              │
│  ┌─────────────────┐      ┌─────────────────────────────┐   │
│  │  StateGraph     │      │     Nodes                    │   │
│  │  - define_state │─────▶│  - create_react_agent        │   │
│  │  - add_edge     │      │  - ToolNode                  │   │
│  │  - add_node     │      │  - ValidationNode            │   │
│  └─────────────────┘      │  - custom functions          │   │
│                           └─────────────────────────────┘   │
│                                                              │
│  ┌─────────────────┐      ┌─────────────────────────────┐   │
│  │  Checkpointers  │      │     Interrupt Types         │   │
│  │  - MemorySaver  │      │  - interrupt()              │   │
│  │  - SqliteSaver   │      │  - HumanInterrupt           │   │
│  │  - RedisSaver    │      │                             │   │
│  └─────────────────┘      └─────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### Memory Architecture

```
BaseChatMessageHistory
├── InMemoryChatMessageHistory
├── FileChatMessageHistory
├── RedisChatMessageHistory
├── SQLChatMessageHistory
└── Custom implementations

ConversationBufferMemory
├── chat_memory: BaseChatMessageHistory
├── return_messages: bool
├── output_key: str
└── input_key: str
```

## API Reference

### Agent Creation Functions

| Function | Purpose | Key Parameters |
|----------|---------|----------------|
| `create_agent` | Minimal modern agent harness | `model`, `tools`, `system_prompt` |
| `create_react_agent` | Zero-shot ReAct agent | `llm`, `tools`, `prompt` |
| `create_structured_chat_agent` | Multi-input structured chat | `llm`, `tools`, `prompt` |
| `create_openai_functions_agent` | OpenAI function calling | `llm`, `tools`, `prompt` |
| `create_tool_calling_agent` | Tool calling agent | `llm`, `tools`, `prompt` |
| `create_xml_agent` | XML-formatted reasoning | `llm`, `tools`, `prompt` |
| `create_json_chat_agent` | JSON-formatted chat | `llm`, `tools`, `prompt` |

### AgentExecutor

```python
class AgentExecutor(BaseChain):
    def __init__(
        self,
        agent: BaseSingleActionAgent,
        tools: Sequence[BaseTool],
        verbose: bool = False,
        max_iterations: int = 15,
        max_execution_time: float | None = None,
        early_stopping_method: str = "force",
        callbacks: Callbacks = None,
        memory: BaseMemory | None = None,
    )
```

### Tool Decorators

```python
@tool                          # Simple tool with *args
@tool(args_schema=PydanticModel)  # Structured tool with schema
```

### LangGraph Prebuilt

```python
create_react_agent(model, tools, state_schema=None, checkpointer=None)
ToolNode(tools)
ValidationNode(pydantic_models)
interrupt([requests])
```

## Common Issues

### 1. Agent Not Using Tools

**Cause**: Tool descriptions are too vague or don't match LLM's understanding.

**Solution**:
```python
@tool
def search(query: str) -> str:
    """Search the internet for current information about any topic.
    Use when you need factual data or want to verify information.
    Args:
        query: The search query (max 100 characters)
    """
    ...
```

### 2. Infinite Loop in AgentExecutor

**Cause**: `max_iterations` too high or agent keeps retrying same action.

**Solution**:
```python
executor = AgentExecutor(
    agent=agent,
    tools=tools,
    max_iterations=5,  # Lower limit
    early_stopping_method="generate",  # Stop on final answer
)
```

### 3. Memory Not Persisting

**Cause**: Not passing `memory` to `AgentExecutor` or wrong key names.

**Solution**:
```python
memory = ConversationBufferMemory(
    memory_key="chat_history",  # Must match prompt variable
    return_messages=True,
    input_key="input",
    output_key="output"
)

executor = AgentExecutor(
    agent=agent,
    tools=tools,
    memory=memory,  # Pass memory here
)
```

### 4. Callback Not Firing

**Cause**: Passing callbacks to wrong layer (agent vs executor).

**Solution**:
```python
# Callbacks on executor (captures full execution)
executor = AgentExecutor(agent=agent, tools=tools, callbacks=[handler])

# Callbacks on agent (only agent planning)
agent = create_react_agent(llm, tools, callbacks=[handler])
```

### 5. LangGraph Interrupt Not Working

**Cause**: Not configuring interrupt properly or using wrong invoke method.

**Solution**:
```python
# Use stream for interrupt to work properly
for event in app.stream({"messages": [...]}):
    if event.get("interrupt"):
        # Handle interrupt
        break
```

## References

- [LangChain Python Docs](https://docs.langchain.com/oss/python/langchain/overview)
- [LangGraph GitHub](https://github.com/langchain-ai/langgraph)
- [LangChain Core](https://github.com/langchain-ai/langchain/tree/master/libs/core/langchain_core)
- [LangChain Classic Agents](https://github.com/langchain-ai/langchain/tree/master/libs/langchain/langchain_classic/agents)
- [create_react_agent Reference](https://github.com/langchain-ai/langgraph/blob/main/libs/prebuilt/README.md)