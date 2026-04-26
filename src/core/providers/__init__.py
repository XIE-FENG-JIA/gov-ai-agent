"""Provider abstraction layer for LLM backends."""

from ._litellm import LiteLLMProvider
from ._openrouter import EmbeddingError, OpenRouterProvider
from ._protocol import LLMProvider

__all__ = ["EmbeddingError", "LLMProvider", "LiteLLMProvider", "OpenRouterProvider", "make_provider"]

# Providers routed to LiteLLMProvider (default path)
_LITELLM_PROVIDERS = frozenset({
    "ollama", "gemini", "litellm", "openai", "anthropic",
    "azure", "groq", "mistral", "cohere", "local",
})


def make_provider(config: dict) -> LLMProvider:
    """Factory: dispatch config['provider'] to the correct LLMProvider implementation.

    - ``"openrouter"`` → :class:`OpenRouterProvider` (REST embedding + LiteLLM completion)
    - any value in ``_LITELLM_PROVIDERS`` or omitted (default ``"ollama"``) → :class:`LiteLLMProvider`
    - unknown string → :exc:`ValueError`
    """
    provider = config.get("provider", "ollama")
    if provider == "openrouter":
        return OpenRouterProvider(config)
    if provider in _LITELLM_PROVIDERS:
        return LiteLLMProvider(config)
    raise ValueError(
        f"Unknown LLM provider: {provider!r}. "
        f"Known providers: openrouter, {', '.join(sorted(_LITELLM_PROVIDERS))}"
    )
