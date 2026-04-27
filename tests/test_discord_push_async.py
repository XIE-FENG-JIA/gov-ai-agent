"""Tests for _discord_push._post_discord async path (mock httpx)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.api.routes.workflow._discord_push import _post_discord


@pytest.fixture()
def _env_discord(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "Bot-test-token")
    monkeypatch.setenv("DISCORD_ALERT_CHANNEL_ID", "123456789")


@pytest.mark.asyncio
async def test_post_discord_success(_env_discord: None) -> None:
    """201 response → logs info, no exception."""
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        await _post_discord({"embeds": [{"title": "test"}]})

    mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_post_discord_4xx_logs_warning(_env_discord: None) -> None:
    """4xx response → logs warning, no exception raised."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "Forbidden"
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        await _post_discord({"embeds": []})  # should not raise


@pytest.mark.asyncio
async def test_post_discord_timeout_handled(_env_discord: None) -> None:
    """httpx.TimeoutException → caught by typed bucket, no exception propagated."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        await _post_discord({"embeds": []})  # should not raise


@pytest.mark.asyncio
async def test_post_discord_http_error_handled(_env_discord: None) -> None:
    """httpx.HTTPError → caught by typed bucket, no exception propagated."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.HTTPError("connection failed"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        await _post_discord({"embeds": []})  # should not raise


@pytest.mark.asyncio
async def test_post_discord_no_token_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    """No DISCORD_BOT_TOKEN → skip without any HTTP call."""
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_ALERT_CHANNEL_ID", raising=False)

    with patch("httpx.AsyncClient") as mock_cls:
        await _post_discord({"embeds": []})
        mock_cls.assert_not_called()
