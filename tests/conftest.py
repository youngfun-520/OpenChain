"""Pytest configuration and fixtures."""

import tempfile
from unittest.mock import MagicMock

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


@pytest.fixture
def temp_dir():
    """Provides a temporary directory for testing."""
    return tempfile.TemporaryDirectory()


@pytest.fixture
def mock_model_registry():
    """Provides a mock model registry for testing."""
    return MagicMock()