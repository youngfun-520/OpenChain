"""LangGraph node implementations."""
import json
import uuid
from typing import Literal
from openchain.agent.state import AgentState
from openchain.session import SessionManager
from openchain.tools.base import ToolRegistry
from openchain.tools.file_tools import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool, GrepTool
from openchain.tools.bash_tool import BashTool
from openchain.tools.web_tools import WebSearchTool, WebFetchTool
from openchain.security import SecurityChecker, SecurityError


from langchain_core.messages import SystemMessage


def _build_tool_result(call_id: str, tool_name: str, result: dict) -> dict:
    """Build a standardized tool result dict."""
    return {
        "tool_call_id": call_id,
        "tool_name": tool_name,
        "result": result
    }


async def _log_tool_call(
    db, call_id: str, node_id: str, session_id: str,
    tool_name: str, args: dict, result: dict, status: str,
    security_verified: int = 0
) -> None:
    """Insert a tool call audit log entry."""
    await db.execute(
        """INSERT INTO tool_calls
           (call_id, node_id, session_id, tool_name, arguments, result, status,
            security_verified, user_confirmed)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (call_id, node_id, session_id, tool_name,
         json.dumps(args), json.dumps(result), status,
         security_verified, 0)
    )
    await db.commit()

async def node_steering_inject(state: AgentState) -> AgentState:
    """Prepend steering messages as SystemMessage to the message list."""
    messages = list(state["messages"])
    steering = state.get("steering_queue", [])
    for msg in reversed(steering):  # reversed so first in list appears first
        messages.insert(0, SystemMessage(content=f"[Steering directive]: {msg['content']}"))
    return {**state, "messages": messages, "steering_queue": []}


async def node_finalize_followup(state: AgentState) -> AgentState:
    """Clear followup queue after response — messages are presented to user as suggestions."""
    return {**state, "followup_queue": []}


async def node_receive_input(state: AgentState) -> AgentState:
    """Receive user input and create a user message."""
    from langchain_core.messages import HumanMessage
    return {
        **state,
        "messages": state["messages"] + [HumanMessage(content=state["input_message"])]
    }


async def node_save_user_message(state: AgentState) -> AgentState:
    """Persist user input message to the database."""
    from openchain.db import Database
    db = Database()
    await db.initialize()
    node_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO message_nodes
           (node_id, session_id, parent_node_id, role, content)
           VALUES (?, ?, ?, ?, ?)""",
        (node_id, state["session_id"], state.get("parent_node_id"),
         "user", state["input_message"])
    )
    await db.commit()
    await db.close()
    return {**state, "parent_node_id": node_id}


async def node_load_session_context(state: AgentState) -> AgentState:
    """Load session history into messages list (prepend to existing)."""
    sm = SessionManager()
    await sm.initialize()
    nodes = await sm.get_session_nodes(state["session_id"])
    from langchain_core.messages import HumanMessage, AIMessage
    history = []
    for node in nodes:
        if node["role"] == "user":
            history.append(HumanMessage(content=node["content"]))
        elif node["role"] == "assistant":
            history.append(AIMessage(content=node["content"]))
    await sm.close()
    # Prepend history to existing messages (from receive_input)
    return {**state, "messages": history + state.get("messages", [])}


async def node_call_model(state: AgentState) -> AgentState:
    """Call LLM with current messages and tools."""
    import os
    from openchain.model_registry import ModelRegistry

    mr = ModelRegistry()
    mr.validate_model_config(state["model"])
    provider = mr.get_model_provider(state["model"])

    # Get tools from registry and convert to LangChain format
    registry = ToolRegistry()
    # Ensure registry security checker matches workspace
    workspace = state.get("workspace", ".")
    cur_ws = getattr(registry, "_default_workspace", None)
    if cur_ws is None or os.path.abspath(workspace) != os.path.abspath(cur_ws):
        from openchain.tools import reset_registry
        reset_registry(workspace)
        registry = ToolRegistry()  # Refresh after reset
    langchain_tools = registry.get_langchain_tools()

    # Create LLM client based on provider
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(model=state["model"])
    elif provider in ("openai", "deepseek", "minimax"):
        from langchain_openai import ChatOpenAI
        key_env = {
            "openai": "OPENAI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "minimax": "MINIMAX_API_KEY",
        }[provider]
        base_env = {
            "openai": None,
            "deepseek": None,
            "minimax": "MINIMAX_API_BASE",
        }[provider]
        llm = ChatOpenAI(
            model=state["model"],
            api_key=os.getenv(key_env),
            base_url=os.getenv(base_env) if base_env else None,
        )
    else:
        state["error"] = f"Unknown provider: {provider}"
        return state

    if langchain_tools:
        llm = llm.bind_tools(langchain_tools)

    try:
        result = await llm.ainvoke(state["messages"])
        # Extract tool_calls from result message and propagate to state
        msg_tool_calls = []
        if hasattr(result, "tool_calls") and result.tool_calls:
            msg_tool_calls = result.tool_calls
        return {
            **state,
            "messages": state["messages"] + [result],
            "tool_calls": msg_tool_calls
        }
    except Exception as e:
        state["error"] = f"LLMError: {e}"
        return state


def _get_assistant_node_id(state: AgentState) -> str:
    """Get the assistant node ID for the current turn."""
    # The assistant node ID is stored when save_message_node was called for the last assistant message
    # For new turns, we need to get or create the node ID
    return state.get("current_assistant_node_id") or str(uuid.uuid4())


async def node_execute_tools(state: AgentState) -> AgentState:
    """Execute pending tool calls and collect results with audit logging."""
    import asyncio
    from openchain.db import Database

    tool_calls = state.get("tool_calls", [])
    tool_results = []
    current_index = state.get("current_tool_call_index", 0)

    # Get assistant node ID for audit logging
    assistant_node_id = _get_assistant_node_id(state)
    session_id = state["session_id"]
    workspace = state.get("workspace", "")

    # Initialize security checker and tool registry
    sc = SecurityChecker(workspace)
    registry = ToolRegistry()

    # Get DB connection for audit logging
    db = Database()
    await db.initialize()

    for i, tc in enumerate(tool_calls):
        if i < current_index:
            continue

        tool_name = tc.get("name", "unknown")
        # LangChain tool args can be dict or BaseModel
        args = tc.get("args", {})
        if hasattr(args, "model_dump"):
            args = args.model_dump()
        if isinstance(args, dict) and "kwargs" in args:
            args = args["kwargs"]  # StructuredTool wraps args in {"kwargs": {...}}
        call_id = str(uuid.uuid4())

        # Security check for API mode (bash disabled unless explicitly enabled)
        if not sc.check_api_mode(tool_name):
            result = {"status": "error", "message": f"Tool '{tool_name}' is disabled in API mode"}
            state["error"] = f"SecurityError: Tool '{tool_name}' is disabled in API mode"
            tool_results.append(_build_tool_result(call_id, tool_name, result))
            # Log to audit table
            await _log_tool_call(
                db, call_id, assistant_node_id, session_id, tool_name,
                args, result, "failure", security_verified=1 if tool_name == "bash" else 0
            )
            continue

        # Get tool instance - create with correct security checker for workspace
        tool_instance = None
        if tool_name == "read_file":
            tool_instance = ReadFileTool(sc)
        elif tool_name == "write_file":
            tool_instance = WriteFileTool(sc)
        elif tool_name == "edit_file":
            tool_instance = EditFileTool(sc)
        elif tool_name == "list_dir":
            tool_instance = ListDirTool(sc)
        elif tool_name == "grep":
            tool_instance = GrepTool(sc)
        elif tool_name == "bash":
            tool_instance = BashTool(sc)
        elif tool_name == "web_search":
            tool_instance = WebSearchTool()
        elif tool_name == "web_fetch":
            tool_instance = WebFetchTool()

        if not tool_instance:
            result = {"status": "error", "message": f"Tool '{tool_name}' not found"}
            tool_results.append(_build_tool_result(call_id, tool_name, result))
            await _log_tool_call(
                db, call_id, assistant_node_id, session_id, tool_name,
                args, result, "failure", security_verified=0
            )
            continue

        # Execute tool with timeout
        try:
            result = await asyncio.wait_for(
                tool_instance.execute(**args),
                timeout=30
            )
            status = "success" if result.get("status") == "success" else "failure"
        except asyncio.TimeoutError:
            result = {"status": "error", "message": "Tool execution timed out"}
            state["error"] = "TimeoutError: Tool execution timed out"
            status = "failure"
        except SecurityError as e:
            result = {"status": "error", "message": f"Security error: {str(e)}"}
            state["error"] = f"SecurityError: {e}"
            status = "failure"
        except Exception as e:
            result = {"status": "error", "message": f"Execution error: {str(e)}"}
            state["error"] = f"ToolExecutionError: {e}"
            status = "failure"

        tool_results.append(_build_tool_result(call_id, tool_name, result))

        # Log to audit table
        security_verified = 1 if tool_name == "bash" else 0
        await _log_tool_call(
            db, call_id, assistant_node_id, session_id, tool_name,
            args, result, status, security_verified
        )

    await db.close()

    return {
        **state,
        "tool_results": tool_results,
        "current_tool_call_index": len(tool_calls)
    }


async def node_save_message_node(state: AgentState) -> AgentState:
    """Save assistant response to message_nodes table and return updated state."""
    sm = SessionManager()
    await sm.initialize()
    last_message = state["messages"][-1] if state["messages"] else None
    current_assistant_node_id = state.get("current_assistant_node_id")

    if last_message:
        # Extract tool_calls if present
        tool_calls_data = None
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            tool_calls_data = []
            for tc in last_message.tool_calls:
                if isinstance(tc, dict):
                    tool_calls_data.append({"name": tc.get("name"), "args": tc.get("args"), "id": tc.get("id")})
                else:
                    tool_calls_data.append({"name": tc.name, "args": tc.args, "id": tc.id})

        node = await sm.save_assistant_message_node(
            session_id=state["session_id"],
            parent_node_id=state.get("parent_node_id"),
            content=last_message.content if hasattr(last_message, "content") else "",
            tool_calls=tool_calls_data,
            tool_results=state.get("tool_results"),
            model=state["model"]
        )
        current_assistant_node_id = node["node_id"]

    await sm.touch_session(state["session_id"])
    await sm.close()
    return {
        **state,
        "current_assistant_node_id": current_assistant_node_id
    }


async def node_handle_error(state: AgentState) -> AgentState:
    """Handle errors and decide retry or abort."""
    current_retry = state.get("retry_count", 0)
    if current_retry >= 3:
        return {**state, "error": "Max retries exceeded", "retry_count": current_retry}
    return {**state, "error": None, "retry_count": current_retry + 1}


async def node_final_response(state: AgentState) -> AgentState:
    """Output final response (END state)."""
    return state


def route_after_model(state: AgentState) -> Literal["execute_tools", "handle_error", "final_response"]:
    """Route after LLM call: tool_calls -> execute_tools; error -> handle_error; retry exhausted -> final_response."""
    # If tool results pending (tools just executed), go to final_response
    if state.get("tool_results"):
        return "final_response"
    # Check retry count
    if state.get("retry_count", 0) >= 3:
        return "final_response"
    # Check error
    if state.get("error"):
        return "handle_error"
    # Check tool_calls from LLM response
    if state.get("tool_calls"):
        return "execute_tools"
    last_message = state["messages"][-1] if state["messages"] else None
    if last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "execute_tools"
    return "final_response"
