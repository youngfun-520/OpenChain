"""Pytest configuration and fixtures."""
import asyncio
import gc
import tempfile
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    """Ensure any lingering database connections are closed after each test."""
    yield
    # Allow background tasks to complete
    await asyncio.sleep(0.01)
    gc.collect()


@pytest.fixture
def runner():
    """Provides a Click CLI test runner."""
    return CliRunner()


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Provides mock environment variables for testing."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENCHAIN_API_KEYS", "test-key:read,write,admin")


@pytest.fixture
def temp_dir():
    """Provides a temporary directory for testing."""
    return tempfile.TemporaryDirectory()


@pytest.fixture
def mock_model_registry():
    """Provides a mock model registry for testing."""
    return MagicMock()