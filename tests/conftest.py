"""Pytest configuration and fixtures."""

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner():
    """Provides a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_env(monkeypatch):
    """Provides mock environment variables for testing."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")