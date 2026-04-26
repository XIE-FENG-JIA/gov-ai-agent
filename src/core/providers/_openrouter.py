"""OpenRouter-backed provider implementation."""

import json
import socket
from collections.abc import Iterator

import requests

from src.core._openrouter_rest import _LazyLiteLLM, _openrouter_embed_rest
from src.core.constants import LLM_CHECK_TIMEOUT, LLM_GENERATION_TIMEOUT

litellm = _LazyLiteLLM()  # noqa: N816


class EmbeddingError(RuntimeError):
    """Raised when OpenRouter embedding REST calls fail."""


class OpenRouterProvider:
    """OpenRouter provider with LiteLLM completion and direct REST embeddings."""

    def __init__(self, provider_config: dict) -> None:
        self.model = provider_config.get("model", "openai/gpt-4o-mini")
        self.api_key = provider_config.get("api_key")
        self.base_url = provider_config.get("base_url")
        self.embedding_model = provider_config.get(
            "embedding_model",
            "text-embedding-3-small",
        )
        self.embedding_api_key = provider_config.get("embedding_api_key") or self.api_key
        self.embedding_base_url = provider_config.get("embedding_base_url") or self.base_url
        self.model_name = self._completion_model_name()

    def complete(self, prompt: str, **kwargs: object) -> str:
        """Return one completed text string using LiteLLM's OpenRouter path."""
        if not prompt or not prompt.strip():
            return ""

        user_content = prompt
        if "qwen3" in self.model_name.lower():
            user_content = "/no_think\n" + prompt

        response = litellm.completion(
            model=self.model_name,
            messages=[{"role": "user", "content": user_content}],
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=LLM_GENERATION_TIMEOUT,
            **kwargs,
        )
        return response.choices[0].message.content or ""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one OpenRouter REST embedding vector for each non-empty input."""
        embeddings: list[list[float]] = []
        for text in texts:
            if not text or not text.strip():
                embeddings.append([])
                continue
            try:
                embeddings.append(
                    _openrouter_embed_rest(
                        model=self.embedding_model,
                        text=text,
                        api_key=self.embedding_api_key,
                        base_url=self.embedding_base_url,
                        timeout=LLM_CHECK_TIMEOUT,
                    )
                )
            except (
                requests.RequestException,
                json.JSONDecodeError,
                ValueError,
                KeyError,
                OSError,
                socket.timeout,
            ) as exc:
                raise EmbeddingError(str(exc)) from exc
        return embeddings

    def stream(self, prompt: str, **kwargs: object) -> Iterator[str]:
        """Streaming is reserved for a later provider epic task."""
        raise NotImplementedError("OpenRouterProvider.stream is not implemented yet")

    def _completion_model_name(self) -> str:
        if self.model.startswith("openrouter/"):
            return self.model
        return f"openrouter/{self.model}"
