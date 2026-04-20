from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.core.models import PublicGovDoc
from src.sources.fda_api import FdaApiAdapter


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "fda_api" / "notices.json"


@patch("src.sources._common.time.sleep")
@patch("src.sources.fda_api.requests.Session.get")
def test_fda_api_adapter_list_fetch_and_normalize(mock_get: MagicMock, _mock_sleep: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.text = FIXTURE_PATH.read_text(encoding="utf-8")
    mock_response.json.side_effect = ValueError("decode from text fixture")
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    adapter = FdaApiAdapter(rate_limit=0)
    listed = list(adapter.list(limit=3))

    assert len(listed) == 3
    assert listed[0]["id"] == "FDA-001"
    assert listed[1]["title"] == "醫療器材回收資訊更新"
    assert str(listed[2]["date"]) == "2026-04-14"

    raw = adapter.fetch("FDA-002")
    assert raw["Link"] == "/tc/newsContent.aspx?cid=3&id=80002"

    normalized = adapter.normalize(raw)
    assert isinstance(normalized, PublicGovDoc)
    assert normalized.source_id == "FDA-002"
    assert normalized.doc_type == "公告"
    assert normalized.source_url == "https://www.fda.gov.tw/tc/newsContent.aspx?cid=3&id=80002"
    assert "醫療器材回收資訊更新" in normalized.content_md
    assert "批號回收名單" in normalized.content_md
    assert normalized.synthetic is False

    mock_get.assert_called_once()


@patch("src.sources._common.time.sleep")
@patch("src.sources.fda_api.requests.Session.get")
def test_fda_api_adapter_filters_by_since_date(mock_get: MagicMock, _mock_sleep: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.text = FIXTURE_PATH.read_text(encoding="utf-8")
    mock_response.json.side_effect = ValueError("decode from text fixture")
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    adapter = FdaApiAdapter(rate_limit=0)
    listed = list(adapter.list(since_date=date(2026, 4, 18), limit=3))

    assert [item["id"] for item in listed] == ["FDA-001", "FDA-002"]


@patch("src.sources._common.time.sleep")
@patch("src.sources.fda_api.requests.Session.get")
def test_fda_api_adapter_fetch_unknown_id_raises(mock_get: MagicMock, _mock_sleep: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.text = FIXTURE_PATH.read_text(encoding="utf-8")
    mock_response.json.side_effect = ValueError("decode from text fixture")
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    adapter = FdaApiAdapter(rate_limit=0)

    with pytest.raises(KeyError):
        adapter.fetch("UNKNOWN")


@patch("src.sources._common.time.sleep")
@patch("src.sources.fda_api.requests.Session.get")
def test_fda_api_adapter_falls_back_to_local_fixture_on_request_error(
    mock_get: MagicMock,
    _mock_sleep: MagicMock,
) -> None:
    mock_get.side_effect = requests.ConnectionError("offline")

    adapter = FdaApiAdapter(rate_limit=0)
    listed = list(adapter.list(limit=3))

    assert [item["id"] for item in listed] == ["FDA-001", "FDA-002", "FDA-003"]


@patch("src.sources._common.time.sleep")
@patch("src.sources.fda_api.requests.Session.get")
def test_fda_api_adapter_falls_back_to_local_fixture_on_invalid_json(
    mock_get: MagicMock,
    _mock_sleep: MagicMock,
) -> None:
    mock_response = MagicMock()
    mock_response.text = "{not-json}"
    mock_response.json.side_effect = ValueError("decode from bad payload")
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    adapter = FdaApiAdapter(rate_limit=0)
    listed = list(adapter.list(limit=3))

    assert [item["id"] for item in listed] == ["FDA-001", "FDA-002", "FDA-003"]
