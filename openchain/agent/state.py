"""AgentState definition for LangGraph."""
from typing import TypedDict, Optional
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """State for the LangGraph agent.

    Each invoke() call processes ONE user input and returns END.
    Multi-turn conversation is handled by CLI/API outer loop.
    """
    # Session context
    session_id: str
    workspace: str

    # Current input
    input_message: str
    parent_node_id: Optional[str]

    # Model
    model: str

    # Conversation history (LangChain messages)
    messages: list[BaseMessage]

    # Tool execution
    tool_calls: list[dict]
    tool_results: list[dict]
    current_tool_call_index: int

    # Error handling
    error: Optional[str]
    retry_count: int

    # Security context
    security_context: dict

    # Message queues
    steering_queue: list[dict] = []    # [{"id": str, "content": str}, ...]
    followup_queue: list[dict] = []    # [{"id": str, "content": str}, ...]