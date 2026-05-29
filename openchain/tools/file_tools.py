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
            with open(path, "r") as f:
                content = f.read()
            return {"status": "success", "content": content, "path": path}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class WriteFileTool(Tool):
    def __init__(self, security_checker: SecurityChecker):
        super().__init__("write_file", "Write content to file")
        self.sc = security_checker

    async def execute(self, path: str, content: str, **kwargs) -> dict:
        if not self.sc.check_path(path):
            raise SecurityError(f"Path outside workspace: {path}")
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            return {"status": "success", "path": path}
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
            with open(path, "r") as f:
                content = f.read()
            if old not in content:
                return {"status": "error", "message": "Pattern not found"}
            content = content.replace(old, new)
            with open(path, "w") as f:
                f.write(content)
            return {"status": "success", "path": path}
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
            items = os.listdir(path)
            return {"status": "success", "items": items, "path": path}
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
            for root, dirs, files in os.walk(path):
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
                        except:
                            pass
            return {"status": "success", "results": results, "pattern": pattern}
        except Exception as e:
            return {"status": "error", "message": str(e)}