"""Bash execution tool."""
import asyncio
import os
import uuid
from openchain.tools.base import Tool
from openchain.security import SecurityChecker, SecurityError


RESTRICTED_COMMANDS = {
    "curl", "wget", "nc", "netcat", "telnet", "ssh", "scp",
    "ftp", "sftp", "aws", "gcloud", "az", "docker", "kubectl",
    "terraform", "ansible", "python", "python3", "node", "ruby",
    "perl", "bash", "sh", "zsh", "chmod", "chown", "setfacl",
    "wireshark", "tcpdump", "nmap",
}


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

        # Check sandbox mode restrictions
        if os.environ.get("OPENCHAIN_SANDBOX_MODE") == "1":
            cmd_parts = command.strip().split()
            if cmd_parts:
                cmd_base = cmd_parts[0].lower()
                if cmd_base in RESTRICTED_COMMANDS:
                    return {
                        "status": "error",
                        "message": f"Command '{cmd_base}' is restricted in sandbox mode"
                    }

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True
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
            # Kill the entire process group, not just the main process
            try:
                proc.kill()
                await proc.wait()  # Properly wait for process to terminate
            except Exception:
                pass
            return {"status": "error", "message": f"Command timed out after {timeout} seconds"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def confirm(self, call_id: str) -> dict:
        """Confirm a pending dangerous command."""
        if call_id not in self.pending_confirmations:
            return {"status": "error", "message": "Confirmation not found"}
        cmd = self.pending_confirmations.pop(call_id)
        return asyncio.run(self.execute(**cmd))