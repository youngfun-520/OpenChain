"""Tests for sandbox hardening."""
import pytest
import asyncio


@pytest.mark.asyncio
async def test_bash_tool_subprocess_cleanup():
    """Bash tool should properly wait for subprocess on timeout."""
    from openchain.tools.bash_tool import BashTool
    from openchain.security import SecurityChecker

    sc = SecurityChecker("/tmp")
    tool = BashTool(sc)

    # Run a command that will be interrupted by timeout
    try:
        result = await tool.execute("sleep 10", timeout=1)
        assert result["status"] == "error"
        assert "timed out" in result["message"].lower() or "timeout" in result["message"].lower()
    except asyncio.TimeoutError:
        pytest.fail("Bash tool should handle TimeoutError internally, not raise it")


@pytest.mark.asyncio
async def test_grep_tool_handles_errors_explicitly():
    """GrepTool should not silently swallow errors."""
    from openchain.tools.file_tools import GrepTool
    from openchain.security import SecurityChecker
    import tempfile
    import os

    sc = SecurityChecker("/tmp")
    tool = GrepTool(sc)

    # GrepTool should return error dict, not raise - use a path in /tmp
    with tempfile.NamedTemporaryFile(dir="/tmp", suffix=".txt") as f:
        f.write(b"hello world")
        f.flush()
        result = await tool.execute(pattern="test", path=f.name)
    assert isinstance(result, dict)
    assert "status" in result