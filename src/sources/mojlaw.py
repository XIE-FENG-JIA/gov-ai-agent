"""Stub adapter for the Ministry of Justice law database."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

from src.sources.base import BaseSourceAdapter


class MojLawAdapter(BaseSourceAdapter):
    """Adapter shell for https://law.moj.gov.tw/ integration."""

    TODO_API_ENDPOINT = "https://law.moj.gov.tw/api/"

    def list(self, since_date: date | None = None) -> Iterable[str]:
        raise NotImplementedError("TODO: implement MojLaw list() against official endpoint")

    def fetch(self, doc_id: str) -> dict[str, Any]:
        raise NotImplementedError("TODO: implement MojLaw fetch() against official endpoint")

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("TODO: implement MojLaw normalize() mapping")

