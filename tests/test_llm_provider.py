"""Tests for src/core/providers — make_provider factory + LiteLLMProvider + OpenRouterProvider.

T18.4: make_provider factory dispatch
T18.5: llm.py openrouter embedding branch delegates via make_provider
T18.6: ≥ 5 test cases
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.core.providers import (
    LiteLLMProvider,
    LLMProvider,
    OpenRouterProvider,
    make_provider,
)


# ---------------------------------------------------------------------------
# T18.4: factory_dispatch
# ---------------------------------------------------------------------------

class TestMakeProviderFactory:
    def test_factory_dispatch_openrouter(self) -> None:
        """make_provider('openrouter') returns OpenRouterProvider."""
        cfg = {"provider": "openrouter", "model": "openai/gpt-4o-mini", "api_key": "k"}
        prov = make_provider(cfg)
        assert isinstance(prov, OpenRouterProvider)

    def test_factory_dispatch_litellm_ollama(self) -> None:
        """make_provider('ollama') returns LiteLLMProvider (default litellm path)."""
        cfg = {"provider": "ollama", "model": "mistral"}
        prov = make_provider(cfg)
        assert isinstance(prov, LiteLLMProvider)

    def test_factory_dispatch_default(self) -> None:
        """make_provider with no 'provider' key defaults to LiteLLMProvider (ollama)."""
        prov = make_provider({"model": "llama3"})
        assert isinstance(prov, LiteLLMProvider)

    def test_factory_dispatch_gemini(self) -> None:
        """make_provider('gemini') returns LiteLLMProvider."""
        prov = make_provider({"provider": "gemini", "api_key": "k"})
        assert isinstance(prov, LiteLLMProvider)

    def test_factory_dispatch_unknown_raises_value_error(self) -> None:
        """make_provider with unknown provider raises ValueError."""
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            make_provider({"provider": "nonexistent_backend"})

    def test_factory_returns_llm_provider_protocol(self) -> None:
        """Both dispatched types satisfy the LLMProvider protocol (duck-typing check)."""
        for cfg in [
            {"provider": "ollama", "model": "mistral"},
            {"provider": "openrouter", "model": "openai/gpt-4o-mini", "api_key": "k"},
        ]:
            prov = make_provider(cfg)
            assert hasattr(prov, "complete")
            assert hasattr(prov, "embed")
            assert hasattr(prov, "stream")


# ---------------------------------------------------------------------------
# T18.5/T18.6: LiteLLMProvider.complete + embed
# ---------------------------------------------------------------------------

class TestLiteLLMProviderComplete:
    def test_litellm_complete_returns_string(self) -> None:
        """LiteLLMProvider.complete() returns the content from litellm."""
        cfg = {"provider": "ollama", "model": "mistral"}
        prov = LiteLLMProvider(cfg)

        fake_response = MagicMock()
        fake_response.choices[0].message.content = "hello"

        with patch("src.core.providers._litellm.litellm") as mock_litellm:
            mock_litellm.completion.return_value = fake_response
            result = prov.complete("Say hello")

        assert result == "hello"

    def test_litellm_complete_empty_prompt_returns_empty(self) -> None:
        """LiteLLMProvider.complete('') returns '' without calling litellm."""
        prov = LiteLLMProvider({"provider": "ollama", "model": "mistral"})
        with patch("src.core.providers._litellm.litellm") as mock_litellm:
            result = prov.complete("   ")
        mock_litellm.completion.assert_not_called()
        assert result == ""


class TestLiteLLMProviderEmbed:
    def test_litellm_embed_returns_vectors(self) -> None:
        """LiteLLMProvider.embed() returns list of float lists per text."""
        cfg = {"provider": "ollama", "model": "mistral", "embedding_model": "llama3.1:8b"}
        prov = LiteLLMProvider(cfg)

        fake_response = MagicMock()
        fake_response.data = [{"embedding": [0.1, 0.2, 0.3]}]

        with patch("src.core.providers._litellm.litellm") as mock_litellm:
            mock_litellm.embedding.return_value = fake_response
            result = prov.embed(["hello world"])

        assert len(result) == 1
        assert result[0] == [0.1, 0.2, 0.3]

    def test_litellm_embed_empty_text_appends_empty_list(self) -> None:
        """LiteLLMProvider.embed(['']) returns [[]] without calling litellm."""
        prov = LiteLLMProvider({"provider": "ollama", "model": "mistral"})
        with patch("src.core.providers._litellm.litellm") as mock_litellm:
            result = prov.embed([""])
        mock_litellm.embedding.assert_not_called()
        assert result == [[]]


# ---------------------------------------------------------------------------
# T18.6: OpenRouterProvider.embed success/failure
# ---------------------------------------------------------------------------

class TestOpenRouterProviderEmbed:
    def test_openrouter_embed_success(self) -> None:
        """OpenRouterProvider.embed() returns vectors from _openrouter_embed_rest."""
        cfg = {"provider": "openrouter", "model": "openai/gpt-4o-mini", "api_key": "test-key"}
        prov = OpenRouterProvider(cfg)

        with patch("src.core.providers._openrouter._openrouter_embed_rest") as mock_rest:
            mock_rest.return_value = [0.5, 0.6, 0.7]
            result = prov.embed(["test text"])

        assert result == [[0.5, 0.6, 0.7]]

    def test_openrouter_embed_failure_raises_embedding_error(self) -> None:
        """OpenRouterProvider.embed() wraps REST failures in EmbeddingError."""
        from src.core.providers import EmbeddingError
        cfg = {"provider": "openrouter", "model": "openai/gpt-4o-mini", "api_key": "test-key"}
        prov = OpenRouterProvider(cfg)

        with patch("src.core.providers._openrouter._openrouter_embed_rest") as mock_rest:
            mock_rest.side_effect = ValueError("bad response")
            with pytest.raises(EmbeddingError):
                prov.embed(["test text"])
