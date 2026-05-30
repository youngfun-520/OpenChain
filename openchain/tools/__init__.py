"""OpenChain tools subpackage.

This module initializes the tool registry with all available tools.
Tools are registered at import time.
"""
from openchain.tools.base import ToolRegistry
from openchain.tools.file_tools import (
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    ListDirTool,
    GrepTool,
)
from openchain.tools.bash_tool import BashTool
from openchain.tools.web_tools import WebSearchTool, WebFetchTool
from openchain.security import SecurityChecker

# Initialize registry singleton
_registry = ToolRegistry()

# Default workspace is current directory (will be overridden by agent's workspace)
_default_security_checker = SecurityChecker(".")

# Register file tools
_registry.register(ReadFileTool(_default_security_checker))
_registry.register(WriteFileTool(_default_security_checker))
_registry.register(EditFileTool(_default_security_checker))
_registry.register(ListDirTool(_default_security_checker))
_registry.register(GrepTool(_default_security_checker))

# Register bash tool
_registry.register(BashTool(_default_security_checker))

# Register web tools
_registry.register(WebSearchTool())
_registry.register(WebFetchTool())


def get_registry() -> ToolRegistry:
    """Get the tool registry instance."""
    return _registry


def reset_registry(workspace: str = "."):
    """Reset registry with a new security checker for the given workspace.

    This should be called when the agent's workspace changes.
    """
    global _registry, _default_security_checker

    _default_security_checker = SecurityChecker(workspace)

    # Re-create all tools with new security checker (force new singleton)
    _registry = ToolRegistry(force_new=True)
    _registry._default_workspace = workspace

    _registry.register(ReadFileTool(_default_security_checker))
    _registry.register(WriteFileTool(_default_security_checker))
    _registry.register(EditFileTool(_default_security_checker))
    _registry.register(ListDirTool(_default_security_checker))
    _registry.register(GrepTool(_default_security_checker))
    _registry.register(BashTool(_default_security_checker))
    _registry.register(WebSearchTool())
    _registry.register(WebFetchTool())