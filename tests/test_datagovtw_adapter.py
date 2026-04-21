from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.core.models import PublicGovDoc
from src.sources.datagovtw import DataGovTwAdapter


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "datagovtw"


def _fixture_datasets() -> list[dict]:
    datasets: list[dict] = []
    for path in sorted(FIXTURE_DIR.glob("*.json")):
        datasets.append(json.loads(path.read_text(encoding="utf-8")))
    return datasets


@patch("src.sources._common.time.sleep")
@patch("src.sources.datagovtw.requests.Session.post")
def test_datagovtw_adapter_list_fetch_and_normalize(mock_post: MagicMock, _mock_sleep: MagicMock) -> None:
    datasets = _fixture_datasets()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "success": True,
        "payload": {"search_count": len(datasets), "search_result": datasets},
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response

    adapter = DataGovTwAdapter(rate_limit=0)
    listed = list(adapter.list(limit=3))

    assert len(listed) == 3
    assert listed[0]["id"] == "1001--resource-1001-json--mohw-1140001"
    assert listed[1]["title"] == "衛生福利部公告更新長照機構評鑑資料提報"
    assert str(listed[2]["date"]) == "2026-04-16"

    raw = adapter.fetch("1002--resource-1002-csv--moda-1140101")
    assert raw["source_agency"] == "數位發展部"
    assert raw["source_doc_no"] == "數位政府字第1140101號"
    assert raw["dataset_title"] == "政府公文附件格式指引"

    normalized = adapter.normalize(raw)
    assert isinstance(normalized, PublicGovDoc)
    assert normalized.source_id == "1002--resource-1002-csv--moda-1140101"
    assert normalized.source_doc_no == "數位政府字第1140101號"
    assert normalized.source_url == "https://moda.gov.tw/press/1140101"
    assert normalized.doc_type == "公告"
    assert "政府公文附件格式指引" in normalized.content_md
    assert "數位發展部" in normalized.content_md
    assert "114年6月30日前完成檢測" in normalized.content_md
    assert normalized.synthetic is False

    mock_post.assert_called_once()


@patch("src.sources._common.time.sleep")
@patch("src.sources.datagovtw.requests.Session.post")
def test_datagovtw_adapter_filters_by_since_date(mock_post: MagicMock, _mock_sleep: MagicMock) -> None:
    datasets = _fixture_datasets()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "success": True,
        "payload": {"search_count": len(datasets), "search_result": datasets},
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response

    adapter = DataGovTwAdapter(rate_limit=0)
    listed = list(adapter.list(since_date=date(2026, 4, 15), limit=3))

    assert [item["id"] for item in listed] == [
        "1001--resource-1001-json--mohw-1140001",
        "1001--resource-1001-json--mohw-1140002",
        "1002--resource-1002-csv--moda-1140101",
    ]


@patch("src.sources._common.time.sleep")
@patch("src.sources.datagovtw.requests.Session.post")
def test_datagovtw_adapter_fetch_unknown_id_raises(mock_post: MagicMock, _mock_sleep: MagicMock) -> None:
    datasets = _fixture_datasets()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "success": True,
        "payload": {"search_count": len(datasets), "search_result": datasets},
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response

    adapter = DataGovTwAdapter(rate_limit=0)

    with pytest.raises(KeyError):
        adapter.fetch("UNKNOWN")


@patch("src.sources._common.time.sleep")
@patch("src.sources.datagovtw.requests.Session.post")
def test_datagovtw_adapter_falls_back_to_local_fixtures_on_request_error(
    mock_post: MagicMock,
    _mock_sleep: MagicMock,
) -> None:
    mock_post.side_effect = requests.ConnectionError("offline")

    adapter = DataGovTwAdapter(rate_limit=0)
    listed = list(adapter.list(limit=3))

    assert [item["id"] for item in listed] == [
        "1001--resource-1001-json--mohw-1140001",
        "1001--resource-1001-json--mohw-1140002",
        "1002--resource-1002-csv--moda-1140101",
    ]
    assert adapter.fetch("1001--resource-1001-json--mohw-1140001")["_fixture_fallback"] is True


@patch("src.sources._common.time.sleep")
@patch("src.sources.datagovtw.requests.Session.post")
def test_datagovtw_adapter_retries_direct_connection_after_proxy_error(
    mock_post: MagicMock,
    _mock_sleep: MagicMock,
) -> None:
    datasets = _fixture_datasets()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "success": True,
        "payload": {"search_count": len(datasets), "search_result": datasets},
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.side_effect = [requests.exceptions.ProxyError("proxy down"), mock_response]

    adapter = DataGovTwAdapter(rate_limit=0)
    listed = list(adapter.list(limit=1))

    assert [item["id"] for item in listed] == ["1001--resource-1001-json--mohw-1140001"]
    assert adapter.fetch("1001--resource-1001-json--mohw-1140001")["_fixture_fallback"] is False
    assert adapter.session.trust_env is False
    assert mock_post.call_count == 2


@patch("src.sources._common.time.sleep")
@patch("src.sources.datagovtw.requests.Session.post")
def test_datagovtw_adapter_falls_back_to_local_fixtures_on_invalid_json(
    mock_post: MagicMock,
    _mock_sleep: MagicMock,
) -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.side_effect = ValueError("bad json")
    mock_post.return_value = mock_response

    adapter = DataGovTwAdapter(rate_limit=0)
    listed = list(adapter.list(limit=3))

    assert [item["id"] for item in listed] == [
        "1001--resource-1001-json--mohw-1140001",
        "1001--resource-1001-json--mohw-1140002",
        "1002--resource-1002-csv--moda-1140101",
    ]


@patch("src.sources._common.time.sleep")
@patch("src.sources.datagovtw.requests.Session.post")
def test_datagovtw_adapter_skips_metadata_only_resource_rows(mock_post: MagicMock, _mock_sleep: MagicMock) -> None:
    datasets = _fixture_datasets()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "success": True,
        "payload": {"search_count": len(datasets), "search_result": datasets},
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response

    adapter = DataGovTwAdapter(rate_limit=0)
    listed = list(adapter.list(limit=10))

    assert all(not item["id"].startswith("1003--") for item in listed)
