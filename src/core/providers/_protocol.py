"""Protocols for LLM provider implementations."""

from collections.abc import Iterator
from typing import Protocol


class LLMProvider(Protocol):
    """Uniform interface for completion, embedding, and streaming providers."""

    def complete(self, prompt: str, **kwargs: object) -> str:
        """Return one completed text string for a prompt.

        Implementations accept a text prompt plus provider-specific keyword
        options. Provider failures should propagate as the existing domain or
        provider exceptions so callers can keep their current error handling.
        """

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text.

        The output order must match the input order. Provider failures should
        propagate as the existing embedding/domain exceptions.
        """

    def stream(self, prompt: str, **kwargs: object) -> Iterator[str]:
        """Yield completion text chunks for a prompt.

        Implementations accept a text prompt plus provider-specific keyword
        options. Providers that do not support streaming should raise
        NotImplementedError.
        """
