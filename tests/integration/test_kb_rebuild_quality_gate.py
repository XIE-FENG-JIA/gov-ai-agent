"""Integration tests: kb quality-gate against live sources.

Gated by GOV_AI_RUN_INTEGRATION=1 — default skip so CI never blocks on live APIs.
Tests run mojlaw + executive_yuan_rss through QualityGate.evaluate() and verify
that real live records pass the gate without raising QualityGateError.
"""

from __future__ import annotations

import os

import pytest

from src.sources.executive_yuan_rss import ExecutiveYuanRssAdapter
from src.sources.mojlaw import MojLawAdapter
from src.sources.quality_gate import GateReport, QualityGate, QualityGateError


pytestmark = pytest.mark.integration


def _require_live_integration() -> None:
    if os.getenv("GOV_AI_RUN_INTEGRATION") != "1":
        pytest.skip("set GOV_AI_RUN_INTEGRATION=1 to run live quality-gate integration tests")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_live_records(adapter, *, limit: int):
    """Fetch and normalize up to *limit* records from *adapter*."""
    docs = list(adapter.list(limit=limit))[:limit]
    records = []
    for item in docs:
        source_id = str(item.get("id", "")).strip()
        if not source_id:
            continue
        try:
            raw = adapter.fetch(source_id)
            normalized = adapter.normalize(raw)
            records.append(normalized)
        except Exception:  # noqa: BLE001 — tolerate individual record fetch errors in integration
            pass
    return records


# ---------------------------------------------------------------------------
# mojlaw — Ministry of Justice law database
# ---------------------------------------------------------------------------

def test_mojlaw_quality_gate_passes_live_records() -> None:
    """Live mojlaw records should pass the quality gate."""
    _require_live_integration()

    adapter = MojLawAdapter()
    records = _fetch_live_records(adapter, limit=5)
    assert records, "mojlaw returned no live documents — check network / API"

    gate = QualityGate(
        expected_min_records=1,
        freshness_window_days=365,
        allow_fallback=False,
    )
    report = gate.evaluate(records, adapter_name="mojlaw")

    assert isinstance(report, GateReport)
    assert report.adapter == "mojlaw"
    assert report.records_in == len(records)
    assert report.records_out > 0
    assert 0.0 <= report.pass_rate <= 1.0
    assert report.duration_seconds >= 0.0


def test_mojlaw_quality_gate_rejects_below_floor() -> None:
    """QualityGate must raise LiveIngestBelowFloor when record count falls below expected_min_records."""
    _require_live_integration()
    from src.sources.quality_gate import LiveIngestBelowFloor

    adapter = MojLawAdapter()
    records = _fetch_live_records(adapter, limit=1)
    # Request 100 minimum but only supply 1
    gate = QualityGate(expected_min_records=100)
    with pytest.raises(LiveIngestBelowFloor) as exc_info:
        gate.evaluate(records[:1], adapter_name="mojlaw")

    assert exc_info.value.adapter_name == "mojlaw"
    assert exc_info.value.actual < 100


# ---------------------------------------------------------------------------
# executive_yuan_rss — Executive Yuan RSS feed
# ---------------------------------------------------------------------------

def test_executive_yuan_rss_quality_gate_passes_live_records() -> None:
    """Live executive_yuan_rss records should pass the quality gate."""
    _require_live_integration()

    adapter = ExecutiveYuanRssAdapter()
    records = _fetch_live_records(adapter, limit=5)
    assert records, "executive_yuan_rss returned no live documents — check network / RSS"

    gate = QualityGate(
        expected_min_records=1,
        freshness_window_days=365,
        allow_fallback=False,
    )
    report = gate.evaluate(records, adapter_name="executiveyuanrss")

    assert isinstance(report, GateReport)
    assert report.records_in == len(records)
    assert report.records_out > 0
    assert report.pass_rate == 1.0


def test_executive_yuan_rss_gate_report_contains_valid_timestamp() -> None:
    """GateReport timestamp should be timezone-aware UTC."""
    _require_live_integration()
    from datetime import timezone

    adapter = ExecutiveYuanRssAdapter()
    records = _fetch_live_records(adapter, limit=2)
    if not records:
        pytest.skip("executive_yuan_rss returned no live documents")

    gate = QualityGate(expected_min_records=1, freshness_window_days=365)
    report = gate.evaluate(records, adapter_name="executiveyuanrss")

    assert report.timestamp.tzinfo is not None
    assert report.timestamp.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# Combined — both sources in one pass (mirrors gov-ai kb rebuild --quality-gate)
# ---------------------------------------------------------------------------

def test_multi_source_quality_gate_reports_collected() -> None:
    """Running gate over both sources returns two GateReport objects without raising."""
    _require_live_integration()

    sources = [
        ("mojlaw", MojLawAdapter()),
        ("executiveyuanrss", ExecutiveYuanRssAdapter()),
    ]

    reports: list[GateReport] = []
    for adapter_name, adapter in sources:
        records = _fetch_live_records(adapter, limit=3)
        if not records:
            pytest.skip(f"{adapter_name} returned no live documents — network may be unavailable")
        gate = QualityGate(expected_min_records=1, freshness_window_days=365, allow_fallback=False)
        report = gate.evaluate(records, adapter_name=adapter_name)
        reports.append(report)

    assert len(reports) == 2
    for report in reports:
        assert isinstance(report, GateReport)
        assert report.pass_rate == 1.0, f"{report.adapter} pass_rate < 1.0: {report}"
