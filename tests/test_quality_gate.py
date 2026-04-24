from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.core.models import PublicGovDoc
from src.sources.quality_gate import (
    GateReport,
    LiveIngestBelowFloor,
    QualityGate,
    SchemaIntegrityError,
    StaleRecord,
    SyntheticContamination,
)


def _make_doc(**overrides: object) -> PublicGovDoc:
    payload = {
        "source_id": "MOHW-001",
        "source_url": "https://example.gov.tw/docs/001",
        "source_agency": "衛生福利部",
        "source_doc_no": "衛部資字第001號",
        "source_date": date(2026, 4, 20),
        "doc_type": "公告",
        "raw_snapshot_path": None,
        "crawl_date": date.today(),
        "content_md": "# 測試文件",
        "synthetic": False,
        "fixture_fallback": False,
    }
    payload.update(overrides)
    return PublicGovDoc(**payload)


def test_quality_gate_returns_report_for_valid_records() -> None:
    gate = QualityGate(expected_min_records=2, freshness_window_days=30, allow_fallback=False)

    report = gate.evaluate([_make_doc(), _make_doc(source_id="MOHW-002")], "mohw_rss")

    assert isinstance(report, GateReport)
    assert report.adapter == "mohw_rss"
    assert report.records_in == 2
    assert report.records_out == 2
    assert report.rejected_by == {}
    assert report.pass_rate == 1.0
    assert report.duration_seconds >= 0


def test_quality_gate_raises_when_batch_is_below_floor() -> None:
    gate = QualityGate(expected_min_records=2)

    with pytest.raises(LiveIngestBelowFloor) as exc_info:
        gate.evaluate([_make_doc()], "mohw_rss")

    assert exc_info.value.adapter_name == "mohw_rss"
    assert exc_info.value.actual == 1
    assert exc_info.value.expected_min_records == 2


def test_quality_gate_from_adapter_name_uses_quality_policy_defaults() -> None:
    gate = QualityGate.from_adapter_name("ExecutiveYuanRSS")

    assert gate.expected_min_records == 5
    assert gate.freshness_window_days == 14
    assert gate.allow_fallback is False


def test_quality_gate_raises_schema_integrity_error_for_missing_provenance_fields() -> None:
    gate = QualityGate()
    invalid_doc = _make_doc(source_doc_no=None, source_date=None)

    with pytest.raises(SchemaIntegrityError) as exc_info:
        gate.evaluate([invalid_doc], "mohw_rss")

    assert exc_info.value.record_id == "MOHW-001"
    assert exc_info.value.missing_fields == ["source_doc_no", "source_date"]


def test_quality_gate_raises_on_synthetic_contamination() -> None:
    gate = QualityGate()

    with pytest.raises(SyntheticContamination) as exc_info:
        gate.evaluate([_make_doc(synthetic=True)], "mohw_rss")

    assert exc_info.value.record_id == "MOHW-001"


def test_quality_gate_raises_on_fixture_fallback_when_disabled() -> None:
    gate = QualityGate(allow_fallback=False)

    with pytest.raises(StaleRecord) as exc_info:
        gate.evaluate([_make_doc(fixture_fallback=True)], "mohw_rss")

    assert exc_info.value.record_id == "MOHW-001"
    assert "fixture fallback" in exc_info.value.reason


def test_quality_gate_raises_on_stale_crawl_date() -> None:
    gate = QualityGate(freshness_window_days=30)
    stale_date = date.today() - timedelta(days=31)

    with pytest.raises(StaleRecord) as exc_info:
        gate.evaluate([_make_doc(crawl_date=stale_date)], "mohw_rss")

    assert exc_info.value.record_id == "MOHW-001"
    assert stale_date.isoformat() in exc_info.value.reason
