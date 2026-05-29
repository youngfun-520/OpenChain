"""Multi-model registry with validation."""
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

PROVIDER_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}

PLACEHOLDER_VALUES = {"", "your_api_key_here", "your-key-here", "sk-ant-..."}
PLACEHOLDER_PATTERNS = ["your_", "your-key", "placeholder"]


def _is_valid_key(key: str) -> bool:
    """Check if an API key looks real (not a placeholder)."""
    if not key or key in PLACEHOLDER_VALUES:
        return False
    lower = key.lower()
    if any(p in lower for p in PLACEHOLDER_PATTERNS):
        return False
    return True

PROVIDER_MODELS = {
    "anthropic": ["claude-sonnet-4-7", "claude-opus-4-7", "claude-haiku-4-5"],
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
    "deepseek": ["deepseek-chat"],
}

DEFAULT_MODEL = None  # Resolved dynamically


class ModelNotFoundError(Exception):
    """Model not found or not configured."""
    pass


class ModelRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._available_models = self._discover_models()

    def _discover_models(self) -> list[str]:
        """Discover available models based on API keys."""
        models = []
        for provider, key_env in PROVIDER_KEYS.items():
            key = os.getenv(key_env, "")
            if _is_valid_key(key):
                models.extend(PROVIDER_MODELS.get(provider, []))
        return models

    def get_available_models(self) -> list[str]:
        return self._available_models

    def get_default_model(self) -> str:
        """Get default model (first available or from env)."""
        env_model = os.getenv("OPENCHAIN_DEFAULT_MODEL")
        if env_model and env_model in self._available_models:
            return env_model
        if self._available_models:
            return self._available_models[0]
        raise ModelNotFoundError(
            "错误：未检测到有效的 API key\n\n"
            "请选择以下任一方式配置：\n\n"
            "方式 1: 编辑 .env 文件，设置以下任一 key：\n"
            "  ANTHROPIC_API_KEY=sk-ant-...\n"
            "  OPENAI_API_KEY=sk-...\n"
            "  DEEPSEEK_API_KEY=sk-...\n\n"
            "方式 2: 设置环境变量：\n"
            "  export ANTHROPIC_API_KEY=sk-ant-...\n\n"
            "获取 API key: https://console.anthropic.com/ (Anthropic)\n"
            "获取 API key: https://platform.openai.com/ (OpenAI)\n"
            "获取 API key: https://platform.deepseek.com/ (DeepSeek)"
        )

    def resolve_model(self, requested: str, session_override: Optional[str] = None) -> str:
        """Return session_override if valid, else requested, else default."""
        if session_override:
            try:
                self.validate_model_config(session_override)
                return session_override
            except ModelNotFoundError:
                pass
        try:
            self.validate_model_config(requested)
            return requested
        except ModelNotFoundError:
            return self.get_default_model()

    def validate_model_config(self, model: str):
        """Validate that a model is configured."""
        if model not in self._available_models:
            raise ModelNotFoundError(
                f"Model '{model}' not available. "
                f"Available: {self._available_models}"
            )

    def get_model_provider(self, model: str) -> str:
        """Get provider name for a model."""
        for provider, models in PROVIDER_MODELS.items():
            if model in models:
                return provider
        raise ModelNotFoundError(f"Unknown model: {model}")