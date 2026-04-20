from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.core.models import PublicGovDoc
from src.sources.mohw_rss import MohwRssAdapter


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "mohw_rss" / "feed.xml"


@patch("src.sources.mohw_rss.time.sleep")
@patch("src.sources.mohw_rss.requests.Session.get")
def test_mohw_rss_adapter_list_fetch_and_normalize(mock_get: MagicMock, _mock_sleep: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.text = FIXTURE_PATH.read_text(encoding="utf-8")
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    adapter = MohwRssAdapter(rate_limit=0)
    listed = list(adapter.list(limit=3))

    assert len(listed) == 3
    assert listed[0]["id"] == "mohw-news-001"
    assert listed[1]["title"] == "食安聯防專案啟動"
    assert str(listed[2]["date"]) == "2026-04-14"

    raw = adapter.fetch("mohw-news-002")
    assert raw["link"] == "https://www.mohw.gov.tw/cp-16-80002-1.html"

    normalized = adapter.normalize(raw)
    assert isinstance(normalized, PublicGovDoc)
    assert normalized.source_id == "mohw-news-002"
    assert normalized.doc_type == "公告"
    assert normalized.source_url == "https://www.mohw.gov.tw/cp-16-80002-1.html"
    assert "食安聯防專案啟動" in normalized.content_md
    assert "跨部會啟動食安聯防專案" in normalized.content_md
    assert normalized.synthetic is False

    mock_get.assert_called_once()


@patch("src.sources.mohw_rss.time.sleep")
@patch("src.sources.mohw_rss.requests.Session.get")
def test_mohw_rss_adapter_filters_by_since_date(mock_get: MagicMock, _mock_sleep: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.text = FIXTURE_PATH.read_text(encoding="utf-8")
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    adapter = MohwRssAdapter(rate_limit=0)
    listed = list(adapter.list(since_date=date(2026, 4, 17), limit=3))

    assert [item["id"] for item in listed] == ["mohw-news-001", "mohw-news-002"]


@patch("src.sources.mohw_rss.time.sleep")
@patch("src.sources.mohw_rss.requests.Session.get")
def test_mohw_rss_adapter_fetch_unknown_id_raises(mock_get: MagicMock, _mock_sleep: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.text = FIXTURE_PATH.read_text(encoding="utf-8")
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    adapter = MohwRssAdapter(rate_limit=0)

    with pytest.raises(KeyError):
        adapter.fetch("UNKNOWN")


@patch("src.sources.mohw_rss.time.sleep")
@patch("src.sources.mohw_rss.requests.Session.get")
def test_mohw_rss_adapter_falls_back_to_local_fixture_on_request_error(
    mock_get: MagicMock,
    _mock_sleep: MagicMock,
) -> None:
    mock_get.side_effect = requests.ConnectionError("offline")

    adapter = MohwRssAdapter(rate_limit=0)
    listed = list(adapter.list(limit=3))

    assert [item["id"] for item in listed] == ["mohw-news-001", "mohw-news-002", "mohw-news-003"]
