"""Shared request helpers for fixture-backed public source adapters."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import TypeVar

import requests


DEFAULT_USER_AGENT = "GovAI-Agent/1.0 (research; contact: local-dev)"

T = TypeVar("T")


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


def with_fixture_fallback(request_loader: Callable[[], T], fallback_loader: Callable[[requests.RequestException], T]) -> T:
    """Run the live request first and fall back to local fixtures on request errors."""
    try:
        return request_loader()
    except requests.RequestException as exc:
        return fallback_loader(exc)
