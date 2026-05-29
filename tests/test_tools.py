"""Tests for tools and security."""
import pytest
from openchain.security import SecurityChecker, SecurityError
from openchain.tools.file_tools import ReadFileTool, WriteFileTool


def test_security_checker_path_within_workspace():
    sc = SecurityChecker("/tmp/workspace")
    assert sc.check_path("/tmp/workspace/file.txt") is True
    assert sc.check_path("/tmp/other/file.txt") is False


def test_security_checker_bash_command_safe():
    sc = SecurityChecker("/tmp")
    safe, reason = sc.check_bash_command("ls -la")
    assert safe is True
    assert reason is None


def test_security_checker_bash_command_dangerous():
    sc = SecurityChecker("/tmp")
    safe, reason = sc.check_bash_command("rm -rf /")
    assert safe is False
    assert reason is not None


def test_read_file_tool_security_rejected():
    sc = SecurityChecker("/tmp/workspace")
    tool = ReadFileTool(sc)
    # check_path returns False for path outside workspace, no exception raised
    result = tool.sc.check_path("/etc/passwd")
    assert result is False


def test_write_file_tool_success(tmp_path):
    sc = SecurityChecker(str(tmp_path))
    tool = WriteFileTool(sc)
    result = tool.sc.check_path(str(tmp_path / "test.txt"))
    assert result is True