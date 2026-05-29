"""Tests for CLI."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from click.testing import CliRunner
from openchain.cli import chat as chat_cmd


def test_cli_chat_command():
    """Test that chat command is accessible."""
    runner = CliRunner()

    with patch('openchain.cli.SessionManager') as mock_sm_class, \
         patch('openchain.cli.ModelRegistry') as mock_mr_class, \
         patch('openchain.cli.build_graph') as mock_build_graph:

        # Setup mocks
        mock_sm = MagicMock()
        mock_sm_class.return_value = mock_sm
        mock_sm.initialize = AsyncMock()
        mock_sm.create_session = AsyncMock(return_value={"session_id": "test-session-id"})
        mock_sm.close = AsyncMock()

        mock_mr = MagicMock()
        mock_mr_class.return_value = mock_mr
        mock_mr.get_default_model.return_value = "test-model"

        mock_graph = MagicMock()
        mock_build_graph.return_value = mock_graph
        mock_graph.ainvoke = AsyncMock(return_value={"messages": []})

        # Run with mocked input
        result = runner.invoke(chat_cmd, input="/quit\n")
        assert result.exit_code == 0