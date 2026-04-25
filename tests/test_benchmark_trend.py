"""Tests for scripts/benchmark_trend.py"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from benchmark_trend import (
    append_entry,
    check_regression,
    load_eval_result,
    main,
    make_trend_entry,
)


SAMPLE_RESULT = {
    "corpus": "benchmark/mvp30_corpus.json",
    "api_base": "http://127.0.0.1:8000",
    "summary": {
        "total": 2,
        "success_count": 2,
        "success_rate": 1.0,
        "goal_met_count": 0,
        "goal_met_rate": 0.0,
        "avg_score": 0.85,
        "by_doc_type": {"函": {"total": 2, "success": 2, "goal_met": 0, "avg_score": 0.85}},
        "top_issue_categories": [],
    },
    "results": [],
}


class TestLoadEvalResult:
    def test_loads_valid_file(self, tmp_path):
        f = tmp_path / "eval.json"
        f.write_text(json.dumps(SAMPLE_RESULT), encoding="utf-8")
        data = load_eval_result(f)
        assert data["summary"]["avg_score"] == 0.85

    def test_raises_on_missing_summary(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text(json.dumps({"results": []}), encoding="utf-8")
        with pytest.raises(ValueError, match="No 'summary'"):
            load_eval_result(f)

    def test_raises_on_invalid_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{not valid json}", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_eval_result(f)


class TestMakeTrendEntry:
    def test_basic_fields(self):
        entry = make_trend_entry(SAMPLE_RESULT, "benchmark/eval.json")
        assert entry["avg_score"] == 0.85
        assert entry["total"] == 2
        assert entry["success_rate"] == 1.0
        assert entry["goal_met_rate"] == 0.0
        assert entry["by_doc_type"] == {"函": 0.85}
        assert entry["source_file"] == "benchmark/eval.json"
        assert "date" in entry
        assert "run_id" in entry

    def test_run_id_from_filename(self):
        entry = make_trend_entry(SAMPLE_RESULT, "benchmark/blind_eval_results.afterfix17.limit2.json")
        assert entry["run_id"] == "blind_eval_results.afterfix17.limit2"


class TestCheckRegression:
    def test_no_regression_when_file_missing(self, tmp_path):
        trend = tmp_path / "trend.jsonl"
        entry = {"avg_score": 0.85}
        is_reg, _ = check_regression(trend, entry)
        assert is_reg is False

    def test_no_regression_when_score_improves(self, tmp_path):
        trend = tmp_path / "trend.jsonl"
        trend.write_text(json.dumps({"avg_score": 0.80, "date": "2026-01-01"}) + "\n", encoding="utf-8")
        entry = {"avg_score": 0.85}
        is_reg, _ = check_regression(trend, entry)
        assert is_reg is False

    def test_regression_detected_on_large_drop(self, tmp_path):
        trend = tmp_path / "trend.jsonl"
        trend.write_text(json.dumps({"avg_score": 0.90, "date": "2026-01-01"}) + "\n", encoding="utf-8")
        entry = {"avg_score": 0.78}  # ~13% drop
        is_reg, msg = check_regression(trend, entry)
        assert is_reg is True
        assert "REGRESSION" in msg
        assert "0.90" in msg or "0.9" in msg

    def test_no_regression_at_exact_threshold(self, tmp_path):
        trend = tmp_path / "trend.jsonl"
        trend.write_text(json.dumps({"avg_score": 0.90, "date": "2026-01-01"}) + "\n", encoding="utf-8")
        entry = {"avg_score": 0.81}  # exactly 10% drop is not > threshold
        is_reg, _ = check_regression(trend, entry)
        assert is_reg is False

    def test_skips_malformed_lines(self, tmp_path):
        trend = tmp_path / "trend.jsonl"
        trend.write_text("{bad json}\n" + json.dumps({"avg_score": 0.90}) + "\n", encoding="utf-8")
        entry = {"avg_score": 0.78}
        is_reg, _ = check_regression(trend, entry)
        assert is_reg is True

    def test_no_regression_on_empty_file(self, tmp_path):
        trend = tmp_path / "trend.jsonl"
        trend.write_text("", encoding="utf-8")
        entry = {"avg_score": 0.78}
        is_reg, _ = check_regression(trend, entry)
        assert is_reg is False


class TestAppendEntry:
    def test_appends_to_new_file(self, tmp_path):
        trend = tmp_path / "trend.jsonl"
        entry = {"avg_score": 0.85, "run_id": "test"}
        append_entry(trend, entry)
        lines = trend.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["avg_score"] == 0.85

    def test_appends_to_existing_file(self, tmp_path):
        trend = tmp_path / "trend.jsonl"
        append_entry(trend, {"avg_score": 0.80, "run_id": "first"})
        append_entry(trend, {"avg_score": 0.85, "run_id": "second"})
        lines = trend.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2

    def test_creates_parent_dirs(self, tmp_path):
        trend = tmp_path / "sub" / "dir" / "trend.jsonl"
        append_entry(trend, {"avg_score": 0.85})
        assert trend.exists()


class TestMain:
    def test_returns_2_on_missing_file(self, tmp_path):
        rc = main(["nonexistent.json", "--trend-file", str(tmp_path / "trend.jsonl")])
        assert rc == 2

    def test_returns_2_on_bad_json(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{bad}", encoding="utf-8")
        rc = main([str(bad), "--trend-file", str(tmp_path / "trend.jsonl")])
        assert rc == 2

    def test_returns_0_on_success(self, tmp_path):
        f = tmp_path / "eval.json"
        f.write_text(json.dumps(SAMPLE_RESULT), encoding="utf-8")
        trend = tmp_path / "trend.jsonl"
        rc = main([str(f), "--trend-file", str(trend)])
        assert rc == 0
        lines = trend.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

    def test_returns_1_on_regression(self, tmp_path):
        f = tmp_path / "eval.json"
        low_score = json.loads(json.dumps(SAMPLE_RESULT))
        low_score["summary"]["avg_score"] = 0.60
        f.write_text(json.dumps(low_score), encoding="utf-8")
        trend = tmp_path / "trend.jsonl"
        trend.write_text(json.dumps({"avg_score": 0.90, "date": "2026-01-01"}) + "\n", encoding="utf-8")
        rc = main([str(f), "--trend-file", str(trend)])
        assert rc == 1

    def test_dry_run_does_not_write(self, tmp_path):
        f = tmp_path / "eval.json"
        f.write_text(json.dumps(SAMPLE_RESULT), encoding="utf-8")
        trend = tmp_path / "trend.jsonl"
        rc = main([str(f), "--trend-file", str(trend), "--dry-run"])
        assert rc == 0
        assert not trend.exists()
