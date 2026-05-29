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

async def node_steering_inject(state: AgentState) -> AgentState:
    """Prepend steering messages as SystemMessage to the message list."""
    messages = list(state["messages"])
    steering = state.get("steering_queue", [])
    for msg in reversed(steering):  # reversed so first in list appears first
        messages.insert(0, SystemMessage(content=f"[Steering directive]: {msg['content']}"))
    return {"messages": messages, "steering_queue": []}


async def node_finalize_followup(state: AgentState) -> AgentState:
    """Clear followup queue after response — messages are presented to user as suggestions."""
    return {"followup_queue": []}


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
    await sm.close()
    return {**state, "messages": messages}


async def node_call_model(state: AgentState) -> AgentState:
    """Call LLM with current messages and tools."""
    from openchain.model_registry import ModelRegistry
    from langchain_anthropic import ChatAnthropic

    mr = ModelRegistry()
    mr.validate_model_config(state["model"])

    # Get tools from registry and convert to LangChain format
    registry = ToolRegistry()
    langchain_tools = registry.get_langchain_tools()

    llm = ChatAnthropic(model=state["model"])
    if langchain_tools:
        llm = llm.bind_tools(langchain_tools)

    try:
        result = await llm.ainvoke(state["messages"])
        return {
            **state,
            "messages": state["messages"] + [result]
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
        call_id = str(uuid.uuid4())

        # Security check for API mode (bash disabled unless explicitly enabled)
        if not sc.check_api_mode(tool_name):
            result = {"status": "error", "message": f"Tool '{tool_name}' is disabled in API mode"}
            state["error"] = f"SecurityError: Tool '{tool_name}' is disabled in API mode"
            tool_results.append({
                "tool_call_id": call_id,
                "tool_name": tool_name,
                "result": result
            })
            # Log to audit table
            await db.execute(
                """INSERT INTO tool_calls
                   (call_id, node_id, session_id, tool_name, arguments, result, status,
                    security_verified, user_confirmed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (call_id, assistant_node_id, session_id, tool_name,
                 json.dumps(args), json.dumps(result), "failure",
                 1 if tool_name == "bash" else 0, 0)
            )
            await db.commit()
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
            tool_results.append({
                "tool_call_id": call_id,
                "tool_name": tool_name,
                "result": result
            })
            await db.execute(
                """INSERT INTO tool_calls
                   (call_id, node_id, session_id, tool_name, arguments, result, status,
                    security_verified, user_confirmed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (call_id, assistant_node_id, session_id, tool_name,
                 json.dumps(args), json.dumps(result), "failure", 0, 0)
            )
            await db.commit()
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

        tool_results.append({
            "tool_call_id": call_id,
            "tool_name": tool_name,
            "result": result
        })

        # Log to audit table
        security_verified = 1 if tool_name == "bash" else 0
        await db.execute(
            """INSERT INTO tool_calls
               (call_id, node_id, session_id, tool_name, arguments, result, status,
                security_verified, user_confirmed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (call_id, assistant_node_id, session_id, tool_name,
             json.dumps(args), json.dumps(result), status, security_verified, 0)
        )
        await db.commit()

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
            tool_calls_data = [
                {"name": tc.name, "args": tc.args, "id": tc.id}
                for tc in last_message.tool_calls
            ]

        node = await sm.save_assistant_message_node(
            session_id=state["session_id"],
            parent_node_id=state.get("parent_node_id"),
            content=last_message.content if hasattr(last_message, "content") else "",
            tool_calls=tool_calls_data,
            tool_results=state.get("tool_results"),
            model=state["model"]
        )
        current_assistant_node_id = node["node_id"]

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
    """Route based on whether model returned tool calls or error."""
    # Check error first — route to error handler if set
    if state.get("error"):
        return "handle_error"
    # Then check if model requested tool execution
    # Check state["tool_calls"] first (set by save_message_node from message.tool_calls)
    if state.get("tool_calls"):
        return "execute_tools"
    # Also check last_message.tool_calls as fallback
    last_message = state["messages"][-1] if state["messages"] else None
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "execute_tools"
    return "final_response"