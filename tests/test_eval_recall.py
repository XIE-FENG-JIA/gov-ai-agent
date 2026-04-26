"""Tests for scripts/eval_recall.py — T-EPIC-19-T19.2-EVAL-RECALL-IMPL."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ── import the script module ──────────────────────────────────────────────────
_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "eval_recall.py"
_spec = importlib.util.spec_from_file_location("eval_recall", _SCRIPT)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["eval_recall"] = _mod  # register before exec so @dataclass can resolve __module__
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]


# ── helpers ───────────────────────────────────────────────────────────────────

def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")


# ── load_eval_set ─────────────────────────────────────────────────────────────

def test_load_eval_set_parses_valid_pairs(tmp_path: Path) -> None:
    f = tmp_path / "eval.jsonl"
    _write_jsonl(f, [
        {"query": "Q1", "expected_doc_id": "doc-001"},
        {"query": "Q2", "expected_doc_id": "doc-002"},
    ])
    pairs, errors = _mod.load_eval_set(f)
    assert len(pairs) == 2
    assert errors == []
    assert pairs[0].query == "Q1"
    assert pairs[0].expected_doc_id == "doc-001"


def test_load_eval_set_skips_blank_lines(tmp_path: Path) -> None:
    f = tmp_path / "eval.jsonl"
    f.write_text('{"query":"Q1","expected_doc_id":"doc-001"}\n\n', encoding="utf-8")
    pairs, errors = _mod.load_eval_set(f)
    assert len(pairs) == 1
    assert errors == []


def test_load_eval_set_reports_missing_query(tmp_path: Path) -> None:
    f = tmp_path / "eval.jsonl"
    _write_jsonl(f, [{"expected_doc_id": "doc-001"}])
    pairs, errors = _mod.load_eval_set(f)
    assert len(pairs) == 0
    assert any("missing query" in e for e in errors)


def test_load_eval_set_reports_malformed_json(tmp_path: Path) -> None:
    f = tmp_path / "eval.jsonl"
    f.write_text("{not valid json}\n", encoding="utf-8")
    pairs, errors = _mod.load_eval_set(f)
    assert len(pairs) == 0
    assert any("malformed JSON" in e for e in errors)


# ── compute_recall ────────────────────────────────────────────────────────────

def _make_pairs(n: int) -> list:
    return [_mod.RecallEvalPair(query=f"Q{i}", expected_doc_id=f"doc-{i:03d}") for i in range(1, n + 1)]


def test_compute_recall_perfect_hit_at_k1() -> None:
    pairs = _make_pairs(2)

    def search_fn(query: str, k: int) -> list[dict]:
        idx = int(query[1:])
        return [{"id": f"doc-{idx:03d}"}]

    metrics, rows = _mod.compute_recall(pairs, search_fn, max_k=5)
    assert metrics["recall@1"] == pytest.approx(1.0)
    assert metrics["recall@5"] == pytest.approx(1.0)
    assert all(r["hit_rank"] == 1 for r in rows)


def test_compute_recall_miss_returns_zero() -> None:
    pairs = _make_pairs(2)

    def search_fn(query: str, k: int) -> list[dict]:
        return [{"id": "doc-999"}]

    metrics, rows = _mod.compute_recall(pairs, search_fn, max_k=5)
    assert metrics["recall@1"] == pytest.approx(0.0)
    assert all(r["hit_rank"] is None for r in rows)


def test_compute_recall_hit_beyond_k1_counts_for_k5() -> None:
    pairs = [_mod.RecallEvalPair(query="Q1", expected_doc_id="doc-003")]

    def search_fn(query: str, k: int) -> list[dict]:
        return [{"id": "doc-001"}, {"id": "doc-002"}, {"id": "doc-003"}]

    metrics, _ = _mod.compute_recall(pairs, search_fn, max_k=5)
    assert metrics["recall@1"] == pytest.approx(0.0)
    assert metrics["recall@3"] == pytest.approx(1.0)
    assert metrics["recall@5"] == pytest.approx(1.0)


# ── build_report / dry-run ────────────────────────────────────────────────────

def test_build_report_dry_run(tmp_path: Path) -> None:
    eval_path = tmp_path / "eval.jsonl"
    _write_jsonl(eval_path, [{"query": "Q1", "expected_doc_id": "doc-001"}])
    report = _mod.build_report(eval_path=eval_path, max_k=5, dry_run=True)
    assert report["embedding_model"] == "dry-run"
    assert report["n_eval"] == 1
    assert report["recall@1"] is None
    assert report["details"] == []


def test_build_report_empty_eval_set_raises(tmp_path: Path) -> None:
    eval_path = tmp_path / "empty.jsonl"
    eval_path.write_text("", encoding="utf-8")
    with pytest.raises(RuntimeError, match="no valid eval pairs"):
        _mod.build_report(eval_path=eval_path, max_k=5, dry_run=True)


# ── main() ────────────────────────────────────────────────────────────────────

def test_main_dry_run_writes_report(tmp_path: Path) -> None:
    eval_path = tmp_path / "eval.jsonl"
    _write_jsonl(eval_path, [{"query": "Q1", "expected_doc_id": "doc-001"}])
    output = tmp_path / "report.json"
    rc = _mod.main(["--eval-set", str(eval_path), "--output", str(output), "--dry-run"])
    assert rc == 0
    assert output.exists()
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["embedding_model"] == "dry-run"
    assert data["n_eval"] == 1


def test_main_k_flag_accepted(tmp_path: Path) -> None:
    eval_path = tmp_path / "eval.jsonl"
    _write_jsonl(eval_path, [{"query": "Q1", "expected_doc_id": "doc-001"}])
    output = tmp_path / "report.json"
    rc = _mod.main(["--eval-set", str(eval_path), "--output", str(output), "--dry-run", "--k", "3"])
    assert rc == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["max_k"] == 3


def test_main_invalid_k_returns_error(tmp_path: Path) -> None:
    eval_path = tmp_path / "eval.jsonl"
    _write_jsonl(eval_path, [{"query": "Q1", "expected_doc_id": "doc-001"}])
    output = tmp_path / "report.json"
    rc = _mod.main(["--eval-set", str(eval_path), "--output", str(output), "--dry-run", "--k", "0"])
    assert rc == 1


def test_main_missing_eval_file_returns_error(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    rc = _mod.main(["--eval-set", str(tmp_path / "nonexistent.jsonl"), "--output", str(output)])
    assert rc == 1


# ── _result_doc_ids ───────────────────────────────────────────────────────────

def test_result_doc_ids_from_top_level_id() -> None:
    ids = _mod._result_doc_ids({"id": "doc-001"})
    assert "doc-001" in ids


def test_result_doc_ids_from_metadata() -> None:
    ids = _mod._result_doc_ids({"metadata": {"doc_id": "doc-002"}})
    assert "doc-002" in ids


def test_result_doc_ids_empty_result() -> None:
    ids = _mod._result_doc_ids({})
    assert ids == set()
