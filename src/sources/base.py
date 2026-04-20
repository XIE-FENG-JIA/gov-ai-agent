"""Abstract adapters for public government document sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import date
from typing import Any


class BaseSourceAdapter(ABC):
    """Common contract for external public-document source adapters."""

    @abstractmethod
    def list(self, since_date: date | None = None) -> Iterable[str]:
        """Return source document ids newer than the optional cutoff date."""

    @abstractmethod
    def fetch(self, doc_id: str) -> dict[str, Any]:
        """Fetch one raw document payload from the upstream source."""

    @abstractmethod
    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize an upstream payload into the internal document shape."""

