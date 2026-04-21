from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.core.models import PublicGovDoc
from src.sources.pcc import PccAdapter


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "pcc"
SEARCH_FIXTURE = FIXTURE_DIR / "search.html"


def _response_with_text(text: str) -> MagicMock:
    response = MagicMock()
    response.text = text
    response.raise_for_status = MagicMock()
    response.encoding = "utf-8"
    return response


@patch("src.sources._common.time.sleep")
@patch("src.sources.pcc.requests.Session.get")
def test_pcc_adapter_list_fetch_and_normalize(mock_get: MagicMock, _mock_sleep: MagicMock) -> None:
    mock_get.side_effect = [
        _response_with_text(SEARCH_FIXTURE.read_text(encoding="utf-8")),
        _response_with_text((FIXTURE_DIR / "PCC-002.html").read_text(encoding="utf-8")),
    ]

    adapter = PccAdapter(rate_limit=0)
    listed = list(adapter.list(limit=3))

    assert len(listed) == 3
    assert listed[0]["id"] == "PCC-001"
    assert listed[1]["title"] == "桃園市政府道路養護勞務採購案"
    assert str(listed[2]["date"]) == "2026-04-15"

    raw = adapter.fetch("PCC-002")
    assert raw["agency"] == "桃園市政府工務局"
    assert raw["budget"] == "新臺幣 8,000,000 元"

    normalized = adapter.normalize(raw)
    assert isinstance(normalized, PublicGovDoc)
    assert normalized.source_id == "PCC-002"
    assert normalized.doc_type == "採購公告"
    assert normalized.source_doc_no == "A-113-002"
    assert normalized.source_url == "https://web.pcc.gov.tw/prkms/tender/common/basic/viewTenderDetail?pk=PCC-002"
    assert "道路養護勞務採購案" in normalized.content_md
    assert "年度道路坑洞修補與巡查服務。" in normalized.content_md
    assert normalized.synthetic is False

    assert mock_get.call_count == 2


@patch("src.sources._common.time.sleep")
@patch("src.sources.pcc.requests.Session.get")
def test_pcc_adapter_filters_by_since_date(mock_get: MagicMock, _mock_sleep: MagicMock) -> None:
    mock_get.return_value = _response_with_text(SEARCH_FIXTURE.read_text(encoding="utf-8"))

    adapter = PccAdapter(rate_limit=0)
    listed = list(adapter.list(since_date=date(2026, 4, 18), limit=5))

    assert [item["id"] for item in listed] == ["PCC-001", "PCC-002"]


@patch("src.sources._common.time.sleep")
@patch("src.sources.pcc.requests.Session.get")
def test_pcc_adapter_fetch_unknown_id_raises(mock_get: MagicMock, _mock_sleep: MagicMock) -> None:
    mock_get.return_value = _response_with_text(SEARCH_FIXTURE.read_text(encoding="utf-8"))

    adapter = PccAdapter(rate_limit=0)

    with pytest.raises(KeyError):
        adapter.fetch("UNKNOWN")


@patch("src.sources._common.time.sleep")
@patch("src.sources.pcc.requests.Session.get")
def test_pcc_adapter_falls_back_to_local_fixtures_on_request_error(
    mock_get: MagicMock,
    _mock_sleep: MagicMock,
) -> None:
    mock_get.side_effect = requests.ConnectionError("offline")

    adapter = PccAdapter(rate_limit=0)
    listed = list(adapter.list(limit=3))

    assert [item["id"] for item in listed] == ["PCC-001", "PCC-002", "PCC-003"]

    raw = adapter.fetch("PCC-001")
    assert raw["_fixture_fallback"] is True

    normalized = adapter.normalize(raw)
    assert normalized.fixture_fallback is True
    assert "機房設備採購案" in normalized.content_md
