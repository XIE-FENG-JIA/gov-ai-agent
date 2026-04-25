"""Shared request helpers for fixture-backed public source adapters."""

from __future__ import annotations

import logging
import threading
import time
import urllib.robotparser
from dataclasses import dataclass
from collections.abc import Callable, Mapping
from typing import Any, Generic, TypeVar
from urllib.parse import urlparse

import requests


_logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "GovAI-Agent/1.0 (research; contact: local-dev)"

T = TypeVar("T")


class RobotsDisallowedError(Exception):
    """Raised when a URL is blocked by the site's robots.txt."""


class RobotsCache:
    """Thread-safe robots.txt cache with TTL-based invalidation (TTL = 1 hr).

    Usage::

        cache = RobotsCache()
        if not cache.allowed(url, user_agent):
            raise RobotsDisallowedError(url)
    """

    TTL: float = 3600.0  # seconds

    def __init__(self) -> None:
        self._cache: dict[str, tuple[urllib.robotparser.RobotFileParser | None, float]] = {}
        self._lock = threading.Lock()

    def _fetch_parser(self, base_url: str) -> urllib.robotparser.RobotFileParser | None:
        """Fetch and parse robots.txt for *base_url*; returns None on any failure."""
        rp = urllib.robotparser.RobotFileParser()
        robots_url = base_url.rstrip("/") + "/robots.txt"
        rp.set_url(robots_url)
        try:
            rp.read()
            return rp
        except Exception as exc:  # noqa: BLE001
            _logger.warning(
                "robots.txt fetch failed for %s: %s — defaulting to allow",
                base_url,
                exc,
            )
            return None

    def allowed(self, url: str, user_agent: str = DEFAULT_USER_AGENT) -> bool:
        """Return True if *url* is permitted by the site's robots.txt for *user_agent*.

        Falls back to ``True`` (allow) when robots.txt is unreachable or unparseable,
        and logs a WARNING so the issue is visible without blocking crawls entirely.
        """
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return True  # non-HTTP URLs are always allowed
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        with self._lock:
            entry = self._cache.get(base_url)
            now = time.time()
            if entry is None or (now - entry[1]) > self.TTL:
                parser = self._fetch_parser(base_url)
                self._cache[base_url] = (parser, now)
                entry = self._cache[base_url]
        parser, _ = entry
        if parser is None:
            return True  # parse-fail → allow
        return bool(parser.can_fetch(user_agent, url))


# Module-level singleton used by request_with_proxy_bypass.
_robots_cache = RobotsCache()


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


def request_with_proxy_bypass(
    session: requests.sessions.Session,
    method: str,
    /,
    *args: Any,
    allow_ssl_fallback: bool = False,
    **kwargs: Any,
) -> requests.Response:
    """Retry direct and optional SSL-fallback requests for brittle public endpoints.

    Raises ``RobotsDisallowedError`` if the target URL is blocked by robots.txt.
    """
    # Robots.txt compliance check — must run before any network I/O.
    if args:
        url = str(args[0])
        ua = str(kwargs.get("headers", {}).get("User-Agent", DEFAULT_USER_AGENT))
        if not _robots_cache.allowed(url, ua):
            raise RobotsDisallowedError(
                f"robots.txt disallows {url!r} for user-agent {ua!r}"
            )
    request_fn = getattr(session, method)
    request_kwargs = dict(kwargs)
    bypassed_proxy = False
    bypassed_ssl = False

    while True:
        try:
            return request_fn(*args, **request_kwargs)
        except requests.exceptions.ProxyError:
            if bypassed_proxy or not getattr(session, "trust_env", False):
                raise
            session.trust_env = False
            bypassed_proxy = True
        except requests.exceptions.SSLError:
            if bypassed_ssl or not allow_ssl_fallback or request_kwargs.get("verify") is False:
                raise
            request_kwargs["verify"] = False
            bypassed_ssl = True
