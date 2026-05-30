"""Tool base classes and registry."""
from abc import ABC, abstractmethod
from typing import Any, Optional
import uuid


class Tool(ABC):
    """Base class for all tools."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(self, **kwargs) -> dict:
        """Execute the tool and return result."""
        pass

    def to_langchain_tool(self):
        """Convert to LangChain tool format."""
        from langchain_core.tools import tool
        @tool(self.name, description=self.description)
        async def wrapper(**kwargs):
            return await self.execute(**kwargs)
        return wrapper


class ToolRegistry:
    """Registry for all available tools."""

    _instance = None
    _default_workspace = "."

    def __new__(cls, force_new: bool = False):
        if force_new or cls._instance is None:
            instance = super().__new__(cls)
            instance._tools = {}
            instance._default_workspace = "."
            if force_new:
                return instance
            cls._instance = instance
        return cls._instance

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def get_all(self) -> list[Tool]:
        return list(self._tools.values())

    def get_langchain_tools(self):
        return [t.to_langchain_tool() for t in self._tools.values()]