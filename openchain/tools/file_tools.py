"""File operation tools."""
import os
from pathlib import Path
from openchain.tools.base import Tool
from openchain.security import SecurityChecker, SecurityError


class ReadFileTool(Tool):
    def __init__(self, security_checker: SecurityChecker):
        super().__init__("read_file", "Read file content")
        self.sc = security_checker

    async def execute(self, path: str, **kwargs) -> dict:
        if not self.sc.check_path(path):
            raise SecurityError(f"Path outside workspace: {path}")
        try:
            # Resolve relative to workspace root, not CWD
            full_path = os.path.join(self.sc.workspace_root, path)
            with open(full_path, "r") as f:
                content = f.read()
            return {"status": "success", "content": content, "path": full_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class WriteFileTool(Tool):
    def __init__(self, security_checker: SecurityChecker):
        super().__init__("write_file", "Write content to file")
        self.sc = security_checker

    async def execute(self, path: str, content: str, **kwargs) -> dict:
        if not self.sc.check_path(path):
            raise SecurityError(f"Path outside workspace: {path}")
        if self.sc.readonly:
            return {"status": "error", "message": "Workspace is in read-only mode"}
        try:
            # Resolve relative to workspace root, not CWD
            full_path = os.path.join(self.sc.workspace_root, path)
            Path(full_path).parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, "w") as f:
                f.write(content)
            return {"status": "success", "path": full_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class EditFileTool(Tool):
    def __init__(self, security_checker: SecurityChecker):
        super().__init__("edit_file", "Edit file content")
        self.sc = security_checker

    async def execute(self, path: str, old: str, new: str, **kwargs) -> dict:
        if not self.sc.check_path(path):
            raise SecurityError(f"Path outside workspace: {path}")
        try:
            # Resolve relative to workspace root, not CWD
            full_path = os.path.join(self.sc.workspace_root, path)
            with open(full_path, "r") as f:
                content = f.read()
            if old not in content:
                return {"status": "error", "message": "Pattern not found"}
            content = content.replace(old, new)
            with open(full_path, "w") as f:
                f.write(content)
            return {"status": "success", "path": full_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class ListDirTool(Tool):
    def __init__(self, security_checker: SecurityChecker):
        super().__init__("list_dir", "List directory contents")
        self.sc = security_checker

    async def execute(self, path: str = ".", **kwargs) -> dict:
        if not self.sc.check_path(path):
            raise SecurityError(f"Path outside workspace: {path}")
        try:
            # Resolve relative to workspace root, not CWD
            full_path = os.path.join(self.sc.workspace_root, path)
            items = os.listdir(full_path)
            return {"status": "success", "items": items, "path": full_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class GrepTool(Tool):
    def __init__(self, security_checker: SecurityChecker):
        super().__init__("grep", "Search for pattern in files")
        self.sc = security_checker

    async def execute(self, pattern: str, path: str = ".", **kwargs) -> dict:
        if not self.sc.check_path(path):
            raise SecurityError(f"Path outside workspace: {path}")
        try:
            results = []
            # Resolve relative to workspace root, not CWD
            full_path = os.path.join(self.sc.workspace_root, path)
            for root, dirs, files in os.walk(full_path):
                for file in files:
                    filepath = os.path.join(root, file)
                    if self.sc.check_path(filepath):
                        try:
                            with open(filepath, "r") as f:
                                for i, line in enumerate(f, 1):
                                    if pattern in line:
                                        results.append({
                                            "file": filepath,
                                            "line": i,
                                            "content": line.strip()
                                        })
                        except PermissionError:
                            # Skip files we can't read — this is acceptable
                            continue
                        except Exception as e:
                            # Don't silently swallow — track that we skipped something
                            continue
            return {"status": "success", "results": results, "pattern": pattern}
        except Exception as e:
            return {"status": "error", "message": str(e)}