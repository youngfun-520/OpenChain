"""Bash execution tool."""
import asyncio
import uuid
from openchain.tools.base import Tool
from openchain.security import SecurityChecker, SecurityError


class BashTool(Tool):
    def __init__(self, security_checker: SecurityChecker):
        super().__init__("bash", "Execute shell command")
        self.sc = security_checker
        self.pending_confirmations = {}

    async def execute(self, command: str, timeout: int = 30, **kwargs) -> dict:
        is_safe, reason = self.sc.check_bash_command(command)
        if not is_safe:
            call_id = str(uuid.uuid4())
            self.pending_confirmations[call_id] = {
                "command": command,
                "timeout": timeout
            }
            return {
                "status": "confirmation_required",
                "call_id": call_id,
                "reason": reason,
                "message": f"Dangerous command: {reason}. Confirm to proceed."
            }

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )
            return {
                "status": "success",
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
                "returncode": proc.returncode
            }
        except asyncio.TimeoutError:
            proc.kill()
            return {"status": "error", "message": "Command timed out"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def confirm(self, call_id: str) -> dict:
        """Confirm a pending dangerous command."""
        if call_id not in self.pending_confirmations:
            return {"status": "error", "message": "Confirmation not found"}
        cmd = self.pending_confirmations.pop(call_id)
        return asyncio.run(self.execute(**cmd))