"""Tests for T19.3–T19.5: recall baseline, sensor recall health, unit recall coverage.

All tests use only mocked filesystem/KB — no live KB or GOV_AI_RUN_INTEGRATION
guard needed.  This file satisfies T19.5 acceptance: pytest tests/test_recall_eval.py.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ── import recall_baseline ────────────────────────────────────────────────────
_BASELINE_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "recall_baseline.py"
_bspec = importlib.util.spec_from_file_location("_recall_baseline_t19", _BASELINE_SCRIPT)
assert _bspec and _bspec.loader
_bmod = importlib.util.module_from_spec(_bspec)
sys.modules.setdefault("_recall_baseline_t19", _bmod)
_bspec.loader.exec_module(_bmod)  # type: ignore[union-attr]

# ── import eval_recall (for compute_recall / load_eval_set) ──────────────────
_EVAL_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "eval_recall.py"
_espec = importlib.util.spec_from_file_location("_eval_recall_t19", _EVAL_SCRIPT)
assert _espec and _espec.loader
_emod = importlib.util.module_from_spec(_espec)
sys.modules.setdefault("_eval_recall_t19", _emod)
_espec.loader.exec_module(_emod)  # type: ignore[union-attr]

# ── import sensor_refresh (for check_recall_health) ──────────────────────────
_SENSOR_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sensor_refresh.py"
_sspec = importlib.util.spec_from_file_location("_sensor_refresh_t19", _SENSOR_SCRIPT)
assert _sspec and _sspec.loader
_smod = importlib.util.module_from_spec(_sspec)
sys.modules.setdefault("_sensor_refresh_t19", _smod)
_sspec.loader.exec_module(_smod)  # type: ignore[union-attr]


# ── helpers ───────────────────────────────────────────────────────────────────

def _write_recall_report(path: Path, recall5: float, model: str = "test-model") -> None:
    path.write_text(
        json.dumps({
            "recall@5": recall5,
            "recall@3": recall5,
            "recall@1": recall5,
            "embedding_model": model,
            "n_eval": 10,
        }),
        encoding="utf-8",
    )


def _write_baseline(path: Path, model: str, floor: float, tolerance: float = 0.10) -> None:
    path.write_text(
        json.dumps({model: {"floor": floor, "last_measured": floor, "tolerance": tolerance}}),
        encoding="utf-8",
    )


# ── T19.3: Recall baseline ratchet ───────────────────────────────────────────

def test_recall_baseline_initial_save(tmp_path: Path) -> None:
    path = tmp_path / "recall_baseline.json"
    _bmod.save_recall_baseline("model-a", 0.85, path=path)
    entry = _bmod.read_recall_baseline("model-a", path=path)
    assert entry["floor"] == pytest.approx(0.85)
    assert entry["last_measured"] == pytest.approx(0.85)
    assert entry["tolerance"] == pytest.approx(0.10)


def test_recall_baseline_ratchet_never_increases(tmp_path: Path) -> None:
    """Baseline floor must never increase when recall improves (ratchet-down contract)."""
    path = tmp_path / "recall_baseline.json"
    _bmod.save_recall_baseline("model-a", 0.85, path=path)
    # Recall improved to 0.95 → floor must stay at 0.85, not increase
    _bmod.save_recall_baseline("model-a", 0.95, path=path)
    entry = _bmod.read_recall_baseline("model-a", path=path)
    assert entry["floor"] == pytest.approx(0.85), "floor must not increase when recall improves"
    assert entry["last_measured"] == pytest.approx(0.95)


def test_recall_baseline_ratchet_decreases_on_worse_recall(tmp_path: Path) -> None:
    """Floor decreases when recall worsens (ratchet allows going lower)."""
    path = tmp_path / "recall_baseline.json"
    _bmod.save_recall_baseline("model-a", 0.85, path=path)
    _bmod.save_recall_baseline("model-a", 0.70, path=path)
    entry = _bmod.read_recall_baseline("model-a", path=path)
    assert entry["floor"] == pytest.approx(0.70), "floor must decrease when recall worsens"


def test_recall_baseline_read_missing_model(tmp_path: Path) -> None:
    path = tmp_path / "recall_baseline.json"
    _bmod.save_recall_baseline("model-a", 0.85, path=path)
    entry = _bmod.read_recall_baseline("model-b", path=path)
    assert entry == {}


def test_recall_baseline_read_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "nonexistent_baseline.json"
    entry = _bmod.read_recall_baseline("model-a", path=path)
    assert entry == {}


# ── T19.4: Sensor recall health check ────────────────────────────────────────

def test_check_recall_health_ok(tmp_path: Path) -> None:
    """Recall within tolerance → health check passes."""
    (tmp_path / "scripts").mkdir()
    _write_recall_report(tmp_path / "recall_report.json", 0.85, "test-model")
    _write_baseline(tmp_path / "scripts" / "recall_baseline.json", "test-model", 0.80, 0.10)

    ok, detail = _smod.check_recall_health(tmp_path)
    assert ok, f"expected ok but got violation: {detail}"


def test_check_recall_health_violation_at_11_percent_drop(tmp_path: Path) -> None:
    """Recall drops 11% below floor×(1-tolerance) → soft violation triggered."""
    (tmp_path / "scripts").mkdir()
    # floor=0.80, tolerance=0.10 → threshold=0.72; recall=0.71 triggers violation
    _write_recall_report(tmp_path / "recall_report.json", 0.71, "test-model")
    _write_baseline(tmp_path / "scripts" / "recall_baseline.json", "test-model", 0.80, 0.10)

    ok, detail = _smod.check_recall_health(tmp_path)
    assert not ok, f"expected violation but got ok: {detail}"
    assert "recall" in detail.lower()


def test_check_recall_health_no_report_skips(tmp_path: Path) -> None:
    """Missing recall_report.json → skip gracefully (ok=True)."""
    ok, detail = _smod.check_recall_health(tmp_path)
    assert ok
    assert "skip" in detail.lower()


def test_check_recall_health_no_baseline_skips(tmp_path: Path) -> None:
    """Missing recall_baseline.json → skip gracefully (ok=True)."""
    _write_recall_report(tmp_path / "recall_report.json", 0.70, "test-model")
    ok, detail = _smod.check_recall_health(tmp_path)
    assert ok
    assert "skip" in detail.lower()


# ── T19.5: Recall computation with mock KB ───────────────────────────────────

def test_perfect_recall_at_k1() -> None:
    """All queries hit at rank 1 → recall@1 = 1.0."""
    pairs = [
        _emod.RecallEvalPair(query="Q1", expected_doc_id="doc-001"),
        _emod.RecallEvalPair(query="Q2", expected_doc_id="doc-002"),
    ]

    def search_fn(query: str, k: int) -> list[dict]:
        idx = query[1:]  # "Q1" → "1"
        return [{"id": f"doc-00{idx}"}]

    metrics, rows = _emod.compute_recall(pairs, search_fn, max_k=5)
    assert metrics["recall@1"] == pytest.approx(1.0)
    assert metrics["recall@5"] == pytest.approx(1.0)
    assert all(r["hit_rank"] == 1 for r in rows)


def test_miss_at_k1_hit_at_k3() -> None:
    """Hit at rank 3 → recall@1=0.0, recall@3=1.0."""
    pairs = [_emod.RecallEvalPair(query="Q1", expected_doc_id="doc-003")]

    def search_fn(query: str, k: int) -> list[dict]:
        return [{"id": "doc-001"}, {"id": "doc-002"}, {"id": "doc-003"}]

    metrics, _ = _emod.compute_recall(pairs, search_fn, max_k=5)
    assert metrics["recall@1"] == pytest.approx(0.0)
    assert metrics["recall@3"] == pytest.approx(1.0)
    assert metrics["recall@5"] == pytest.approx(1.0)


def test_jsonl_loader_handles_malformed_lines(tmp_path: Path) -> None:
    """Malformed JSON lines are reported as errors without crashing."""
    f = tmp_path / "bad.jsonl"
    f.write_text(
        '{"query":"Q1","expected_doc_id":"doc-001"}\n'
        "{not valid json}\n"
        '{"query":"Q2","expected_doc_id":"doc-002"}\n',
        encoding="utf-8",
    )
    pairs, errors = _emod.load_eval_set(f)
    assert len(pairs) == 2
    assert len(errors) == 1
    assert "malformed JSON" in errors[0]
