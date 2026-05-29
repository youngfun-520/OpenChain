"""Tests for model registry."""
import os
import pytest
from unittest.mock import patch, MagicMock
from openchain.model_registry import ModelRegistry, ModelNotFoundError


def test_model_registry_singleton():
    mr1 = ModelRegistry()
    mr2 = ModelRegistry()
    assert mr1 is mr2


def test_get_available_models():
    mr = ModelRegistry()
    models = mr.get_available_models()
    assert isinstance(models, list)


def test_validate_model_config_valid():
    mr = ModelRegistry()
    # Test with environment variable
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        mr2 = ModelRegistry.__new__(ModelRegistry)
        mr2._initialized = False
        mr2.__init__()
        # Should not raise for properly configured model
        if mr2._available_models:
            mr2.validate_model_config(mr2._available_models[0])


def test_validate_model_config_invalid():
    mr = ModelRegistry()
    with pytest.raises(ModelNotFoundError):
        mr.validate_model_config("nonexistent-model-xyz")


def test_get_model_provider():
    mr = ModelRegistry()
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        mr2 = ModelRegistry.__new__(ModelRegistry)
        mr2._initialized = False
        mr2.__init__()
        if mr2._available_models:
            provider = mr2.get_model_provider(mr2._available_models[0])
            assert provider == "anthropic"