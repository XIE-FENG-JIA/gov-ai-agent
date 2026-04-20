from __future__ import annotations

import io
import json
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.core.models import PublicGovDoc
from src.sources.mojlaw import MojLawAdapter


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mojlaw"


def _fixture_laws() -> list[dict]:
    laws: list[dict] = []
    for path in sorted(FIXTURE_DIR.glob("*.json")):
        laws.append(json.loads(path.read_text(encoding="utf-8")))
    return laws


def _make_catalog_zip(laws: list[dict]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        payload = json.dumps({"Laws": laws}, ensure_ascii=False).encode("utf-8")
        zf.writestr("ChLaw.json", payload)
    return buffer.getvalue()


@patch("src.sources.mojlaw.time.sleep")
@patch("src.sources.mojlaw.requests.Session.get")
def test_mojlaw_adapter_list_fetch_and_normalize(mock_get: MagicMock, _mock_sleep: MagicMock) -> None:
    laws = _fixture_laws()
    mock_response = MagicMock()
    mock_response.content = _make_catalog_zip(laws)
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    adapter = MojLawAdapter(rate_limit=0)
    listed = list(adapter.list())

    assert len(listed) == 3
    assert listed[0]["id"] == "A0030018"
    assert listed[1]["title"] == "行政程序法"
    assert str(listed[2]["date"]) == "2026-02-01"

    raw = adapter.fetch("A0030055")
    assert raw["LawName"] == "行政程序法"

    normalized = adapter.normalize(raw)
    assert isinstance(normalized, PublicGovDoc)
    assert normalized.source_id == "A0030055"
    assert normalized.source_doc_no == "A0030055"
    assert normalized.doc_type == "法規"
    assert "行政程序法" in normalized.content_md
    assert "第 1 條" in normalized.content_md
    assert normalized.synthetic is False

    mock_get.assert_called_once()


@patch("src.sources.mojlaw.time.sleep")
@patch("src.sources.mojlaw.requests.Session.get")
def test_mojlaw_adapter_filters_by_since_date(mock_get: MagicMock, _mock_sleep: MagicMock) -> None:
    laws = _fixture_laws()
    mock_response = MagicMock()
    mock_response.content = _make_catalog_zip(laws)
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    adapter = MojLawAdapter(rate_limit=0)
    listed = list(adapter.list(since_date=date(2026, 1, 20)))

    assert [item["id"] for item in listed] == ["A0030133"]


@patch("src.sources.mojlaw.time.sleep")
@patch("src.sources.mojlaw.requests.Session.get")
def test_mojlaw_adapter_fetch_unknown_id_raises(mock_get: MagicMock, _mock_sleep: MagicMock) -> None:
    laws = _fixture_laws()
    mock_response = MagicMock()
    mock_response.content = _make_catalog_zip(laws)
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    adapter = MojLawAdapter(rate_limit=0)

    with pytest.raises(KeyError):
        adapter.fetch("UNKNOWN")


@patch("src.sources.mojlaw.time.sleep")
@patch("src.sources.mojlaw.requests.Session.get")
def test_mojlaw_adapter_falls_back_to_local_fixtures_on_request_error(
    mock_get: MagicMock,
    _mock_sleep: MagicMock,
) -> None:
    mock_get.side_effect = requests.exceptions.ProxyError("proxy down")

    adapter = MojLawAdapter(rate_limit=0)
    listed = list(adapter.list(limit=3))

    assert [item["id"] for item in listed] == ["A0030018", "A0030055", "A0030133"]
    assert adapter.fetch("A0030018")["LawName"] == "公文程式條例"
