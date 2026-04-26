"""LiteLLM-backed provider implementation."""

from collections.abc import Iterator
import logging

from src.core._openrouter_rest import _LLM_PROVIDER_EXCEPTIONS, _LazyLiteLLM
from src.core.constants import LLM_CHECK_TIMEOUT, LLM_GENERATION_TIMEOUT

logger = logging.getLogger(__name__)

litellm = _LazyLiteLLM()  # noqa: N816


class LiteLLMProvider:
    """Default provider backed by LiteLLM completion and embedding calls."""

    def __init__(self, provider_config: dict) -> None:
        self.provider = provider_config.get("provider", "ollama")
        self.model = provider_config.get("model", "mistral")
        self.api_key = provider_config.get("api_key")
        self.base_url = provider_config.get("base_url")
        self.embedding_provider = provider_config.get("embedding_provider", self.provider)
        self.embedding_model = provider_config.get("embedding_model", "llama3.1:8b")
        self.embedding_api_key = provider_config.get("embedding_api_key")
        self.embedding_base_url = provider_config.get("embedding_base_url")

        if self.embedding_provider == "ollama" and not self.embedding_base_url:
            self.embedding_base_url = "http://127.0.0.1:11434"
        elif self.embedding_provider == self.provider and not self.embedding_base_url:
            self.embedding_base_url = self.base_url
        if self.embedding_provider != "ollama" and not self.embedding_api_key:
            self.embedding_api_key = self.api_key

        self.model_name = self._completion_model_name()

    def complete(self, prompt: str, **kwargs: object) -> str:
        """Return one completed text string using LiteLLM completion()."""
        if not prompt or not prompt.strip():
            logger.warning("LiteLLM complete received an empty prompt")
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
        """Return one LiteLLM embedding vector for each non-empty input text."""
        if not texts:
            return []

        model_name = self._embedding_model_name()
        api_key = self.embedding_api_key if self.embedding_provider != "ollama" else None
        embeddings: list[list[float]] = []

        for text in texts:
            if not text or not text.strip():
                embeddings.append([])
                continue
            try:
                response = litellm.embedding(
                    model=model_name,
                    input=[text],
                    api_key=api_key,
                    base_url=self.embedding_base_url,
                    timeout=LLM_CHECK_TIMEOUT,
                )
            except _LLM_PROVIDER_EXCEPTIONS:
                raise
            if not response.data:
                embeddings.append([])
            else:
                embeddings.append(response.data[0]["embedding"])
        return embeddings

    def stream(self, prompt: str, **kwargs: object) -> Iterator[str]:
        """Streaming is reserved for a later provider epic task."""
        raise NotImplementedError("LiteLLMProvider.stream is not implemented yet")

    def _completion_model_name(self) -> str:
        if self.provider == "ollama":
            return f"ollama/{self.model}"
        if self.provider == "gemini" and not self.model.startswith("gemini/"):
            return f"gemini/{self.model}"
        if self.provider == "openrouter" and not self.model.startswith("openrouter/"):
            return f"openrouter/{self.model}"
        return self.model

    def _embedding_model_name(self) -> str:
        if self.embedding_provider == "ollama":
            return f"ollama/{self.embedding_model}"
        if self.embedding_provider == "gemini":
            return "gemini/text-embedding-004"
        return self.embedding_model
