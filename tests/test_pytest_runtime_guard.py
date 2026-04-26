"""Unit tests for the pytest runtime regression guard (Epic 20, T20.3).

All tests run without executing live pytest — baseline files are written to
temporary directories.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts/ to path so we can import measure_pytest_runtime directly.
_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from measure_pytest_runtime import update_baseline  # noqa: E402
from sensor_refresh import check_pytest_runtime, SensorReport, build_report  # noqa: E402


# ---------------------------------------------------------------------------
# T20.1 tests — measure_pytest_runtime.update_baseline / dry-run
# ---------------------------------------------------------------------------

class TestMeasurePytestRuntime:
    def test_dry_run_creates_baseline_file(self, tmp_path):
        """Dry-run (last_s=0.0) creates baseline file with correct fields."""
        baseline = tmp_path / "pytest_runtime_baseline.json"
        result = update_baseline(baseline, last_s=0.0)
        assert baseline.exists()
        data = json.loads(baseline.read_text())
        assert "ceiling_s" in data
        assert "last_s" in data
        assert data["last_s"] == 0.0
        assert "tolerance" in data
        assert "measured_at" in data

    def test_ratchet_down_updates_ceiling_when_faster(self, tmp_path):
        """If new run is faster than old ceiling, ceiling_s decreases."""
        baseline = tmp_path / "pytest_runtime_baseline.json"
        # First run: last_s=100, ceiling_s should be 150
        update_baseline(baseline, last_s=100.0)
        data1 = json.loads(baseline.read_text())
        assert data1["ceiling_s"] == pytest.approx(150.0, abs=0.1)

        # Second run is faster (80s < 100s ceiling threshold logic: 80 < 150)
        update_baseline(baseline, last_s=80.0)
        data2 = json.loads(baseline.read_text())
        # New ceiling = 80 * 1.5 = 120 < old 150 → ratchet-down
        assert data2["ceiling_s"] == pytest.approx(120.0, abs=0.1)
        assert data2["last_s"] == pytest.approx(80.0, abs=0.01)

    def test_no_ratchet_up_when_slower(self, tmp_path):
        """If new run is slower than current ceiling, ceiling stays unchanged."""
        baseline = tmp_path / "pytest_runtime_baseline.json"
        # Establish ceiling
        update_baseline(baseline, last_s=100.0)
        data1 = json.loads(baseline.read_text())
        old_ceiling = data1["ceiling_s"]  # 150.0

        # Slower run (200 > ceiling 150) — ceiling must NOT increase
        update_baseline(baseline, last_s=200.0)
        data2 = json.loads(baseline.read_text())
        assert data2["ceiling_s"] == pytest.approx(old_ceiling, abs=0.1)
        assert data2["last_s"] == pytest.approx(200.0, abs=0.01)

    def test_first_run_initialises_ceiling_with_buffer(self, tmp_path):
        """First run sets ceiling_s = last_s × 1.5."""
        baseline = tmp_path / "pytest_runtime_baseline.json"
        update_baseline(baseline, last_s=120.0)
        data = json.loads(baseline.read_text())
        assert data["ceiling_s"] == pytest.approx(180.0, abs=0.1)


# ---------------------------------------------------------------------------
# T20.2 tests — check_pytest_runtime in sensor_refresh
# ---------------------------------------------------------------------------

class TestCheckPytestRuntime:
    def _write_baseline(self, path: Path, ceiling_s: float, last_s: float, tolerance: float = 0.20) -> None:
        data = {"ceiling_s": ceiling_s, "last_s": last_s, "tolerance": tolerance, "measured_at": "2026-01-01T00:00:00+00:00"}
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def test_soft_violation_fires_at_ceiling_times_1_21(self, tmp_path):
        """Soft violation fires when last_s > ceiling_s * (1 + 0.20) = ceiling * 1.20."""
        baseline = tmp_path / "scripts" / "pytest_runtime_baseline.json"
        baseline.parent.mkdir(parents=True)
        ceiling = 100.0
        # last_s = ceiling * 1.21 → exceeds threshold
        self._write_baseline(baseline, ceiling_s=ceiling, last_s=ceiling * 1.21)
        result = check_pytest_runtime(tmp_path)
        assert result["status"] == "violation"
        assert "pytest-runtime-regression" in result.get("detail", "")

    def test_status_ok_when_last_s_within_ceiling(self, tmp_path):
        """Status is 'ok' when last_s <= ceiling_s * (1 + tolerance)."""
        baseline = tmp_path / "scripts" / "pytest_runtime_baseline.json"
        baseline.parent.mkdir(parents=True)
        self._write_baseline(baseline, ceiling_s=100.0, last_s=110.0)  # 110 ≤ 120 → ok
        result = check_pytest_runtime(tmp_path)
        assert result["status"] == "ok"

    def test_missing_baseline_returns_skip(self, tmp_path):
        """If baseline file does not exist, return status='skip' without violation."""
        result = check_pytest_runtime(tmp_path)
        assert result["status"] == "skip"

    def test_violation_wired_into_sensor_soft_violations(self, tmp_path):
        """When check_pytest_runtime returns violation, build_report adds it to violations_soft."""
        # Write baseline that triggers violation
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        baseline = scripts_dir / "pytest_runtime_baseline.json"
        ceiling = 100.0
        data = {"ceiling_s": ceiling, "last_s": ceiling * 1.21, "tolerance": 0.20, "measured_at": "2026-01-01T00:00:00+00:00"}
        baseline.write_text(json.dumps(data) + "\n", encoding="utf-8")

        # Stub out all other data sources so build_report doesn't hit live filesystem
        with patch("sensor_refresh.count_bare_except", return_value=(0, 0, [])), \
             patch("sensor_refresh.scan_fat_files", return_value=([], [])), \
             patch("sensor_refresh.check_fat_ratchet", return_value=(True, "ok")), \
             patch("sensor_refresh.count_corpus", return_value=300), \
             patch("sensor_refresh.count_lines", return_value=100), \
             patch("sensor_refresh.auto_commit_rate", return_value=(25, 1.0)), \
             patch("sensor_refresh.epic6_progress", return_value=(0, 0)), \
             patch("sensor_refresh.active_epic_progress", return_value={"epic_id": "", "done": 0, "total": 0}), \
             patch("sensor_refresh.read_runtime_baseline", return_value=0.0), \
             patch("sensor_refresh.count_marked_done_uncommitted", return_value={"count": 0, "slugs": []}), \
             patch("sensor_refresh.check_recall_health", return_value=(True, "no baseline (skip)")), \
             patch("sensor_refresh.read_ceiling_params", return_value=(0.0, 0.0)):
            report = build_report(tmp_path)

        assert report.pytest_runtime["status"] == "violation"
        assert any("pytest-runtime-regression" in v for v in report.violations_soft)
