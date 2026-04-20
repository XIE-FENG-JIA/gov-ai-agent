from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.core.models import PublicGovDoc
from src.sources.executive_yuan_rss import ExecutiveYuanRssAdapter


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "executive_yuan_rss" / "feed.xml"


@patch("src.sources._common.time.sleep")
@patch("src.sources.executive_yuan_rss.requests.Session.get")
def test_executive_yuan_rss_adapter_list_fetch_and_normalize(mock_get: MagicMock, _mock_sleep: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.text = FIXTURE_PATH.read_text(encoding="utf-8")
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    adapter = ExecutiveYuanRssAdapter(rate_limit=0)
    listed = list(adapter.list(limit=3))

    assert len(listed) == 3
    assert listed[0]["id"] == "ey-news-001"
    assert listed[1]["title"] == "院會通過資料治理精進方案"
    assert str(listed[2]["date"]) == "2026-04-14"

    raw = adapter.fetch("ey-news-002")
    assert raw["link"] == "https://www.ey.gov.tw/Page/ExampleNews2"

    normalized = adapter.normalize(raw)
    assert isinstance(normalized, PublicGovDoc)
    assert normalized.source_id == "ey-news-002"
    assert normalized.doc_type == "新聞稿"
    assert normalized.source_url == "https://www.ey.gov.tw/Page/ExampleNews2"
    assert "資料治理精進方案" in normalized.content_md
    assert "跨部會資料交換" in normalized.content_md
    assert normalized.synthetic is False

    mock_get.assert_called_once()


@patch("src.sources._common.time.sleep")
@patch("src.sources.executive_yuan_rss.requests.Session.get")
def test_executive_yuan_rss_adapter_filters_by_since_date(mock_get: MagicMock, _mock_sleep: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.text = FIXTURE_PATH.read_text(encoding="utf-8")
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    adapter = ExecutiveYuanRssAdapter(rate_limit=0)
    listed = list(adapter.list(since_date=date(2026, 4, 18), limit=3))

    assert [item["id"] for item in listed] == ["ey-news-001", "ey-news-002"]


@patch("src.sources._common.time.sleep")
@patch("src.sources.executive_yuan_rss.requests.Session.get")
def test_executive_yuan_rss_adapter_fetch_unknown_id_raises(mock_get: MagicMock, _mock_sleep: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.text = FIXTURE_PATH.read_text(encoding="utf-8")
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    adapter = ExecutiveYuanRssAdapter(rate_limit=0)

    with pytest.raises(KeyError):
        adapter.fetch("UNKNOWN")


@patch("src.sources._common.time.sleep")
@patch("src.sources.executive_yuan_rss.requests.Session.get")
def test_executive_yuan_rss_adapter_falls_back_to_local_fixture_on_request_error(
    mock_get: MagicMock,
    _mock_sleep: MagicMock,
) -> None:
    mock_get.side_effect = requests.ConnectionError("offline")

    adapter = ExecutiveYuanRssAdapter(rate_limit=0)
    listed = list(adapter.list(limit=3))
    normalized = adapter.normalize(adapter.fetch("ey-news-001"))

    assert [item["id"] for item in listed] == ["ey-news-001", "ey-news-002", "ey-news-003"]
    assert normalized.synthetic is True
    assert normalized.fixture_fallback is True


@patch("src.sources._common.time.sleep")
@patch("src.sources.executive_yuan_rss.requests.Session.get")
def test_executive_yuan_rss_adapter_retries_direct_connection_after_proxy_error(
    mock_get: MagicMock,
    _mock_sleep: MagicMock,
) -> None:
    mock_response = MagicMock()
    mock_response.text = FIXTURE_PATH.read_text(encoding="utf-8")
    mock_response.raise_for_status = MagicMock()
    mock_get.side_effect = [requests.exceptions.ProxyError("proxy down"), mock_response]

    adapter = ExecutiveYuanRssAdapter(rate_limit=0)
    listed = list(adapter.list(limit=1))
    normalized = adapter.normalize(adapter.fetch("ey-news-001"))

    assert [item["id"] for item in listed] == ["ey-news-001"]
    assert normalized.synthetic is False
    assert normalized.fixture_fallback is False
    assert adapter.session.trust_env is False
    assert mock_get.call_count == 2


@patch("src.sources._common.time.sleep")
@patch("src.sources.executive_yuan_rss.requests.Session.get")
def test_executive_yuan_rss_adapter_falls_back_to_local_fixture_on_invalid_xml(
    mock_get: MagicMock,
    _mock_sleep: MagicMock,
) -> None:
    mock_response = MagicMock()
    mock_response.text = "<rss><channel><item></rss"
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    adapter = ExecutiveYuanRssAdapter(rate_limit=0)
    listed = list(adapter.list(limit=3))

    assert [item["id"] for item in listed] == ["ey-news-001", "ey-news-002", "ey-news-003"]
