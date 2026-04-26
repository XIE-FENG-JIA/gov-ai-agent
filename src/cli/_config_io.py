"""config_tools 輔助函式與常數（無 CLI typer 依賴）。"""
import logging

from src.core.llm import LiteLLMProvider

logger = logging.getLogger(__name__)

_CONFIG_TOOL_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError, Exception)

_PROVIDER_TEMPLATES = {
    "ollama": {
        "provider": "ollama",
        "model": "llama3.1:8b",
        "base_url": "http://127.0.0.1:11434",
        "embedding_provider": "ollama",
        "embedding_model": "llama3.1:8b",
        "embedding_base_url": "http://127.0.0.1:11434",
        "api_key": "",
    },
    "gemini": {
        "provider": "gemini",
        "model": "gemini-2.5-pro",
        "api_key": "${GEMINI_API_KEY}",
    },
    "openrouter": {
        "provider": "openrouter",
        "model": "${LLM_MODEL}",
        "api_key": "${LLM_API_KEY}",
        "base_url": "https://openrouter.ai/api/v1",
    },
    "minimax": {
        "provider": "minimax",
        "model": "openai/MiniMax-M2.7",
        "api_key": "${MINIMAX_API_KEY}",
        "base_url": "https://api.minimax.io/v1",
    },
}


def _parse_value(value: str):
    """自動判斷值的類型：布林、整數、浮點數或字串。"""
    if value.lower() in ("true", "yes"):
        return True
    if value.lower() in ("false", "no"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def _mask_sensitive(data, _sensitive_keys=("api_key", "secret", "token", "password")):
    """遞迴遮蔽敏感欄位。"""
    if isinstance(data, dict):
        return {
            k: "***" if any(sk in k.lower() for sk in _sensitive_keys) else _mask_sensitive(v)
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [_mask_sensitive(item) for item in data]
    return data


def test_connectivity(model_id: str, api_key: str) -> bool:
    """嘗試使用模型產生簡短回應以測試連線。"""
    if not api_key:
        return False

    config = {
        "provider": "openrouter",
        "model": model_id,
        "api_key": api_key,
        "base_url": "https://openrouter.ai/api/v1"
    }

    try:
        llm = LiteLLMProvider(config)
        llm.generate("Hi", max_tokens=1)
        return True
    except _CONFIG_TOOL_EXCEPTIONS as exc:
        logger.debug("模型連線測試失敗（%s）: %s", model_id, exc)
        return False
