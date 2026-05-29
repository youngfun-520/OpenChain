"""Tests for enhanced sandbox: sensitive files, read-only mode, restricted bash."""
import pytest
import os

def test_sensitive_files_blocked():
    """SecurityChecker should block access to sensitive files."""
    from openchain.security import SecurityChecker

    sc = SecurityChecker("/tmp/workspace")

    sensitive_files = [
        "/tmp/workspace/.env",
        "/tmp/workspace/id_rsa",
        "/tmp/workspace/secrets.json",
        "/tmp/workspace/.aws/credentials",
        "/tmp/workspace/config.py",
        "/tmp/workspace/.git/config",
        "/tmp/workspace/.npmrc",
        "/tmp/workspace/.pypirc",
    ]

    for path in sensitive_files:
        assert sc.check_path(path) is False, f"Should block: {path}"

def test_normal_files_allowed():
    """Normal files should still be accessible."""
    from openchain.security import SecurityChecker
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        sc = SecurityChecker(tmpdir)
        normal_file = os.path.join(tmpdir, "readme.txt")
        with open(normal_file, "w") as f:
            f.write("hello")
        assert sc.check_path(normal_file) is True

@pytest.mark.asyncio
async def test_read_only_mode_blocks_write():
    """Write operations should be blocked in read-only mode."""
    from openchain.tools.file_tools import WriteFileTool
    from openchain.security import SecurityChecker

    os.environ["OPENCHAIN_READONLY_WORKSPACE"] = "1"

    try:
        sc = SecurityChecker("/tmp")
        tool = WriteFileTool(sc)
        result = await tool.execute(path="/tmp/test.txt", content="hello")
        assert result["status"] == "error"
        assert "read-only" in result["message"] or "readonly" in result["message"].lower()
    finally:
        os.environ.pop("OPENCHAIN_READONLY_WORKSPACE", None)

@pytest.mark.asyncio
async def test_restricted_bash_profile_blocks_commands():
    """Bash commands should be restricted in sandbox mode."""
    from openchain.tools.bash_tool import BashTool
    from openchain.security import SecurityChecker

    os.environ["OPENCHAIN_SANDBOX_MODE"] = "1"
    sc = SecurityChecker("/tmp")
    tool = BashTool(sc)

    # These commands should be blocked in sandbox mode
    restricted = ["curl", "wget", "nc", "telnet", "ssh"]
    for cmd in restricted:
        result = await tool.execute(f"{cmd} https://example.com", timeout=2)
        assert result["status"] == "error", f"{cmd} should be blocked in sandbox mode"
        assert "restricted" in result["message"].lower()

    # Clean up
    os.environ.pop("OPENCHAIN_SANDBOX_MODE", None)

@pytest.mark.asyncio
async def test_normal_bash_allowed_outside_sandbox():
    """Normal bash commands should work outside sandbox mode."""
    from openchain.tools.bash_tool import BashTool
    from openchain.security import SecurityChecker

    # Ensure sandbox mode is off
    os.environ.pop("OPENCHAIN_SANDBOX_MODE", None)
    sc = SecurityChecker("/tmp")
    tool = BashTool(sc)

    result = await tool.execute("echo hello", timeout=5)
    assert result["status"] == "success"

@pytest.mark.asyncio
async def test_dangerous_commands_still_blocked():
    """Even outside sandbox mode, dangerous commands should be blocked."""
    from openchain.tools.bash_tool import BashTool
    from openchain.security import SecurityChecker

    os.environ.pop("OPENCHAIN_SANDBOX_MODE", None)
    sc = SecurityChecker("/tmp")
    tool = BashTool(sc)

    result = await tool.execute("rm -rf /", timeout=5)
    assert result["status"] == "confirmation_required" or result["status"] == "error"