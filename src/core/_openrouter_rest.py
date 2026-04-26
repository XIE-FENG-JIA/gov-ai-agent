"""Internal LLM infrastructure helpers extracted from src.core.llm.

Contains:
- LLM exception hierarchy and _LLM_PROVIDER_EXCEPTIONS bucket
- Lazy LiteLLM loader (_load_litellm, _LazyLiteLLM)
- Local embedder singleton (_LocalEmbedder, sentence-transformers)
- OpenRouter REST embedding helpers (_openrouter_embed_rest)

Kept separate to hold src/core/llm.py below the 350-line fat-gate threshold.
"""
from __future__ import annotations

import logging
import os
import threading
import requests as _requests

from src.core.constants import LLM_CHECK_TIMEOUT

logger = logging.getLogger(__name__)

# ============================================================
# Provider exception bucket
# ============================================================
_LLM_PROVIDER_EXCEPTIONS = (
    ConnectionError,
    OSError,
    RuntimeError,
    TimeoutError,
    ValueError,
    Exception,
)

# ============================================================
# LLM custom exception hierarchy
# ============================================================


class LLMError(Exception):
    """LLM 服務錯誤基礎類別。"""
    pass


class LLMConnectionError(LLMError):
    """無法連線到 LLM 服務。"""
    pass


class LLMAuthError(LLMError):
    """API Key 無效或認證失敗。"""
    pass


class LLMTimeoutError(LLMError):
    """LLM 生成超時。"""
    pass


# ============================================================
# Lazy LiteLLM loader
# ============================================================
_litellm_module = None
_litellm_lock = threading.Lock()


def _load_litellm():
    """Import LiteLLM on first real use, not during API/test collection."""
    global _litellm_module
    if _litellm_module is None:
        with _litellm_lock:
            if _litellm_module is None:
                import litellm as module

                module.suppress_debug_info = True
                module.set_verbose = False
                logging.getLogger("LiteLLM").setLevel(logging.ERROR)
                _litellm_module = module
    return _litellm_module


class _LazyLiteLLM:
    __func__ = None

    def completion(self, *args, **kwargs):
        return _load_litellm().completion(*args, **kwargs)

    def embedding(self, *args, **kwargs):
        return _load_litellm().embedding(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(_load_litellm(), name)

    def __setattr__(self, name: str, value) -> None:
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        object.__delattr__(self, name)


# ============================================================
# Local embedder singleton (sentence-transformers)
# ============================================================


class _LocalEmbedder:
    """使用 sentence-transformers 的本地 embedding 單例。"""
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get(cls, model_name: str = "all-MiniLM-L6-v2") -> "_LocalEmbedder":
        with cls._lock:
            if cls._instance is None or cls._instance._model_name != model_name:
                cls._instance = cls(model_name)
        return cls._instance

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer
        self._model_name = model_name
        self._model = SentenceTransformer(model_name)
        logger.info("本地 embedding 模型已載入: %s", model_name)

    def embed(self, text: str) -> list[float]:
        return self._model.encode(text, normalize_embeddings=True).tolist()


# ============================================================
# OpenRouter REST embedding helpers
# ============================================================
_OPENROUTER_DEFAULT_BASE = "https://openrouter.ai/api/v1"
_EMBEDDING_TRUNCATE_CHARS = 8000


def _truncate_for_embedding(text: str, max_chars: int = _EMBEDDING_TRUNCATE_CHARS) -> str:
    """Truncate text to stay within the free embedding model's context window."""
    return text[:max_chars] if len(text) > max_chars else text


def _openrouter_embed_rest(
    model: str,
    text: str,
    api_key: str | None,
    base_url: str | None = None,
    timeout: int = LLM_CHECK_TIMEOUT,
) -> list[float]:
    """Call OpenRouter REST API for embeddings, bypassing litellm.

    OpenRouter does not expose an embedding endpoint through litellm;
    this function calls the OpenAI-compatible REST API directly.
    """
    _key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
    _base = (base_url or _OPENROUTER_DEFAULT_BASE).rstrip("/")
    resp = _requests.post(
        f"{_base}/embeddings",
        headers={
            "Authorization": f"Bearer {_key}",
            "Content-Type": "application/json",
        },
        json={"model": model, "input": [_truncate_for_embedding(text)]},
        timeout=timeout,
    )
    resp.raise_for_status()
    body = resp.json()
    if "error" in body:
        raise RuntimeError(body["error"].get("message", "OpenRouter embedding error"))
    return body["data"][0]["embedding"]
