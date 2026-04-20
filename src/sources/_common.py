"""Shared request helpers for fixture-backed public source adapters."""

from __future__ import annotations

from dataclasses import dataclass
import time
from collections.abc import Callable, Mapping
from typing import Generic, TypeVar

import requests


DEFAULT_USER_AGENT = "GovAI-Agent/1.0 (research; contact: local-dev)"

T = TypeVar("T")


@dataclass(frozen=True)
class FixtureFallbackResult(Generic[T]):
    """Payload plus whether it came from the local fixture fallback path."""

    value: T
    used_fixture: bool = False


def throttle(last_request_time: float, rate_limit: float) -> float:
    """Sleep until the next request is allowed and return the new timestamp."""
    now = time.time()
    elapsed = now - last_request_time
    if elapsed < rate_limit:
        time.sleep(rate_limit - elapsed)
    return time.time()


def build_headers(*, accept: str, user_agent: str = DEFAULT_USER_AGENT, extra: Mapping[str, str] | None = None) -> dict[str, str]:
    headers = {"User-Agent": user_agent, "Accept": accept}
    if extra:
        headers.update(dict(extra))
    return headers


def with_fixture_fallback(
    request_loader: Callable[[], T],
    fallback_loader: Callable[[Exception], T],
    *,
    handled_exceptions: tuple[type[Exception], ...] = (requests.RequestException,),
) -> FixtureFallbackResult[T]:
    """Run the live request first and fall back to local fixtures on known request/parsing errors."""
    try:
        return FixtureFallbackResult(request_loader(), used_fixture=False)
    except handled_exceptions as exc:
        return FixtureFallbackResult(fallback_loader(exc), used_fixture=True)
