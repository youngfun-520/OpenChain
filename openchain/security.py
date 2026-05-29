"""Security checking for tools."""
import os
import re
from typing import Optional


DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"dd\s+.*of=",
    r":\(\)\s*\{[^}]*:\|:&[^}]*\};",
    r"mkfs",
    r"fdisk",
    r"parted",
    r"shutdown",
    r"reboot",
    r"init\s+\d",
]

CONFIRMATION_COMMANDS = [
    "sudo",
    "rm",
    "dd",
    "mkfs",
    "fdisk",
    "> /dev/",
    "> /dev/null",
]


class SecurityError(Exception):
    """Security check failed."""
    pass


class SecurityChecker:
    def __init__(self, workspace_root: str):
        self.workspace_root = os.path.abspath(workspace_root)

    def check_path(self, path: str) -> bool:
        """Check if path is within workspace using realpath to prevent symlink escapes."""
        try:
            real_path = os.path.realpath(os.path.abspath(path))
            return real_path.startswith(os.path.realpath(self.workspace_root))
        except (OSError, ValueError):
            return False

    def check_bash_command(self, command: str) -> tuple[bool, Optional[str]]:
        """Check if bash command is safe."""
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, command):
                return False, f"Dangerous pattern matched: {pattern}"
        for cmd in CONFIRMATION_COMMANDS:
            if cmd in command:
                return False, f"Command requires confirmation: {cmd}"
        return True, None

    def check_api_mode(self, tool_name: str) -> bool:
        """Check if tool is allowed in API mode."""
        enable_bash = os.getenv("OPENCHAIN_API_ENABLE_BASH", "false").lower() == "true"
        if tool_name == "bash" and not enable_bash:
            return False
        return True