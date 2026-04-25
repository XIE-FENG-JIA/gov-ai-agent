"""Cascade / multi-source quality gate scenario tests.

Covers:
  1. Multi-source fail-stop — first adapter failure halts cascade
  2. Partial pass — some adapters pass, one fails; only successful ones included
  3. Cascade ordering — failure on adapter N does not evaluate adapter N+1
  4. Mixed named errors — each named failure type can appear in a multi-adapter run
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.core.models import PublicGovDoc
from src.sources.quality_gate import (
    GateReport,
    LiveIngestBelowFloor,
    QualityGate,
    QualityGateError,
    SchemaIntegrityError,
    StaleRecord,
    SyntheticContamination,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_doc(**overrides: object) -> PublicGovDoc:
    payload: dict = {
        "source_id": "TEST-001",
        "source_url": "https://example.gov.tw/docs/001",
        "source_agency": "測試機關",
        "source_doc_no": "測字第001號",
        "source_date": date(2026, 4, 1),
        "doc_type": "函",
        "raw_snapshot_path": None,
        "crawl_date": date.today(),
        "content_md": "# 測試",
        "synthetic": False,
        "fixture_fallback": False,
    }
    payload.update(overrides)
    return PublicGovDoc(**payload)


def _run_multi_source_cascade(
    adapter_batches: dict[str, list[PublicGovDoc]],
    *,
    gate: QualityGate | None = None,
    fail_stop: bool = True,
) -> tuple[list[GateReport], list[tuple[str, QualityGateError]]]:
    """Simulate a multi-source cascade gate run.

    Returns (passed_reports, failed_list) where failed_list is
    [(adapter_name, exc), ...] in order of first failure.
    If fail_stop=True, stops at first failure.
    """
    if gate is None:
        gate = QualityGate(expected_min_records=1)

    passed: list[GateReport] = []
    failed: list[tuple[str, QualityGateError]] = []

    for adapter_name, batch in adapter_batches.items():
        try:
            report = gate.evaluate(batch, adapter_name)
            passed.append(report)
        except QualityGateError as exc:
            failed.append((adapter_name, exc))
            if fail_stop:
                break

    return passed, failed


# ---------------------------------------------------------------------------
# Test 1 — Multi-source fail-stop
# ---------------------------------------------------------------------------

def test_cascade_fail_stop_halts_on_first_adapter_failure() -> None:
    """When fail_stop=True, the cascade must stop at the first adapter failure
    and must NOT evaluate subsequent adapters."""
    evaluated_order: list[str] = []

    # We track evaluation by wrapping batches — if the adapter is evaluated its
    # key ends up in evaluated_order via side-effect in the dict iteration.
    # Adapter "b" fails; adapter "c" must NOT be evaluated.
    batches: dict[str, list[PublicGovDoc]] = {
        "source_a": [_make_doc(source_id="A-001")],
        "source_b": [],  # empty → LiveIngestBelowFloor
        "source_c": [_make_doc(source_id="C-001")],
    }

    gate = QualityGate(expected_min_records=1)
    passed, failed = _run_multi_source_cascade(batches, gate=gate, fail_stop=True)

    # Only source_a should have passed; source_b failed; source_c never reached
    assert len(passed) == 1
    assert passed[0].adapter == "source_a"
    assert len(failed) == 1
    assert failed[0][0] == "source_b"
    assert isinstance(failed[0][1], LiveIngestBelowFloor)


# ---------------------------------------------------------------------------
# Test 2 — Partial pass (no fail-stop)
# ---------------------------------------------------------------------------

def test_cascade_partial_pass_collects_all_results_when_fail_stop_disabled() -> None:
    """Without fail_stop, cascade continues past a failure; multiple sources
    contribute independent pass/fail results."""
    stale_date = date.today() - timedelta(days=400)

    batches: dict[str, list[PublicGovDoc]] = {
        "source_good_1": [_make_doc(source_id="G1-001")],
        "source_stale": [_make_doc(source_id="S-001", crawl_date=stale_date)],
        "source_good_2": [_make_doc(source_id="G2-001")],
    }

    gate = QualityGate(expected_min_records=1, freshness_window_days=30)
    passed, failed = _run_multi_source_cascade(batches, gate=gate, fail_stop=False)

    assert len(passed) == 2
    assert {r.adapter for r in passed} == {"source_good_1", "source_good_2"}

    assert len(failed) == 1
    assert failed[0][0] == "source_stale"
    assert isinstance(failed[0][1], StaleRecord)


# ---------------------------------------------------------------------------
# Test 3 — Cascade ordering — failure does not bleed into next adapter
# ---------------------------------------------------------------------------

def test_cascade_ordering_failure_does_not_contaminate_next_adapter() -> None:
    """A SchemaIntegrityError from adapter N must not affect adapter N+1 evaluation.
    The gate is stateless between calls."""
    bad_doc = _make_doc(source_id="BAD-001", source_doc_no=None)  # triggers SchemaIntegrityError

    batches: dict[str, list[PublicGovDoc]] = {
        "adapter_n": [bad_doc],
        "adapter_n_plus_1": [_make_doc(source_id="OK-001")],
    }

    gate = QualityGate(expected_min_records=1)
    passed, failed = _run_multi_source_cascade(batches, gate=gate, fail_stop=False)

    # adapter_n failed with schema error
    assert len(failed) == 1
    assert failed[0][0] == "adapter_n"
    assert isinstance(failed[0][1], SchemaIntegrityError)

    # adapter_n+1 passes cleanly — gate state is not shared
    assert len(passed) == 1
    assert passed[0].adapter == "adapter_n_plus_1"
    assert passed[0].pass_rate == 1.0


# ---------------------------------------------------------------------------
# Test 4 — Mixed named errors across multiple adapters
# ---------------------------------------------------------------------------

def test_cascade_mixed_named_errors_all_four_failure_types() -> None:
    """All four named QualityGate failure types must be raisable in a single
    multi-source run (no fail-stop).  Each failure type is associated with
    exactly one adapter."""
    stale_date = date.today() - timedelta(days=400)

    batches: dict[str, list[PublicGovDoc]] = {
        "below_floor_source": [],  # LiveIngestBelowFloor
        # Pass a dict missing source_date so model_validate raises ValidationError → SchemaIntegrityError
        "schema_bad_source": [{"source_id": "S-001", "source_url": "https://example.gov.tw/bad"}],  # SchemaIntegrityError
        "synthetic_source": [_make_doc(source_id="SY-001", synthetic=True)],  # SyntheticContamination
        "stale_source": [_make_doc(source_id="ST-001", crawl_date=stale_date)],  # StaleRecord
    }

    gate = QualityGate(
        expected_min_records=1,
        freshness_window_days=30,
        allow_fallback=True,
    )
    passed, failed = _run_multi_source_cascade(batches, gate=gate, fail_stop=False)

    assert len(passed) == 0
    assert len(failed) == 4

    failure_types = {type(exc) for _, exc in failed}
    assert failure_types == {
        LiveIngestBelowFloor,
        SchemaIntegrityError,
        SyntheticContamination,
        StaleRecord,
    }

    # Verify adapter-to-error mapping
    error_map = {name: type(exc) for name, exc in failed}
    assert error_map["below_floor_source"] is LiveIngestBelowFloor
    assert error_map["schema_bad_source"] is SchemaIntegrityError
    assert error_map["synthetic_source"] is SyntheticContamination
    assert error_map["stale_source"] is StaleRecord
