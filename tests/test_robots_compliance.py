"""Tests for robots.txt compliance — T-ROBOTS-IMPL.

Three required cases:
1. allow   — URL permitted by robots.txt → allowed() == True
2. disallow — URL blocked by robots.txt  → allowed() == False
3. parse-fail fallback — robots.txt fetch fails → allowed() == True + WARNING logged
"""
from __future__ import annotations

import logging
import urllib.robotparser
from unittest.mock import patch

import pytest

from src.sources._common import DEFAULT_USER_AGENT, RobotsCache, RobotsDisallowedError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_parser(*, disallow: list[str] | None = None) -> urllib.robotparser.RobotFileParser:
    """Build a real RobotFileParser from in-memory content."""
    lines = ["User-agent: *"]
    for path in disallow or []:
        lines.append(f"Disallow: {path}")
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(lines)
    return rp


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_robots_allow() -> None:
    """URL not listed in Disallow → allowed() returns True."""
    parser = _make_parser(disallow=["/private/"])
    rc = RobotsCache()
    with patch.object(rc, "_fetch_parser", return_value=parser):
        assert rc.allowed("https://example.com/public/doc.html", DEFAULT_USER_AGENT) is True


def test_robots_disallow() -> None:
    """URL listed in Disallow → allowed() returns False."""
    parser = _make_parser(disallow=["/private/"])
    rc = RobotsCache()
    with patch.object(rc, "_fetch_parser", return_value=parser):
        assert rc.allowed("https://example.com/private/secret", DEFAULT_USER_AGENT) is False


def test_robots_parse_fail_fallback_to_allow_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    """When robots.txt fetch raises, default to allow=True and emit a WARNING."""
    rc = RobotsCache()
    with patch("urllib.robotparser.RobotFileParser.read", side_effect=OSError("connection refused")):
        with caplog.at_level(logging.WARNING, logger="src.sources._common"):
            result = rc.allowed("https://unreachable.example.com/page", DEFAULT_USER_AGENT)

    assert result is True, "parse-fail should fall back to allow=True"
    assert "robots.txt fetch failed" in caplog.text, "WARNING must be logged on parse failure"


def test_robots_disallow_raises_in_request_with_proxy_bypass() -> None:
    """request_with_proxy_bypass raises RobotsDisallowedError for blocked URLs."""
    from unittest.mock import MagicMock

    from src.sources._common import _robots_cache, request_with_proxy_bypass

    session = MagicMock()
    parser = _make_parser(disallow=["/blocked/"])

    # Temporarily seed the real module-level cache with a disallow parser.
    _robots_cache._cache["https://gov.example.com"] = (parser, 0)  # TTL not expired: use 0 if reset

    # Force TTL expiry workaround: patch allowed() directly on the singleton.
    with patch.object(_robots_cache, "allowed", return_value=False):
        with pytest.raises(RobotsDisallowedError):
            request_with_proxy_bypass(
                session,
                "get",
                "https://gov.example.com/blocked/file",
                headers={"User-Agent": DEFAULT_USER_AGENT},
            )
