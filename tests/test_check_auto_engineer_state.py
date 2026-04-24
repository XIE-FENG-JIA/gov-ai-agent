"""Tests for scripts/check_auto_engineer_state.py."""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "check_auto_engineer_state.py"
_spec = importlib.util.spec_from_file_location("check_auto_engineer_state", _MODULE_PATH)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
check = _mod.check


_FIXED_NOW = datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc)


def _write_state(tmp_path: Path, **fields) -> Path:
    payload = {
        "round": "120",
        "status": "running",
        "pid": "999999",  # unlikely to exist
        "last_update": fields.pop("last_update", "2026-04-24T11:55:00+00:00"),
        **fields,
    }
    p = tmp_path / "state.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_absent_state_returns_absent(tmp_path):
    report = check(tmp_path / "no-such.json", now=_FIXED_NOW)
    assert report["status"] == "absent"
    assert report["recommendation"].startswith("no auto-engineer")


def test_malformed_state_flagged(tmp_path):
    p = tmp_path / "state.json"
    p.write_text("{not valid json", encoding="utf-8")
    report = check(p, now=_FIXED_NOW)
    assert report["status"] == "malformed"


def test_running_fresh_within_threshold(tmp_path):
    # last_update 5 min ago, status running
    p = _write_state(tmp_path, last_update="2026-04-24T11:55:00+00:00")
    report = check(p, threshold_seconds=2 * 3600, now=_FIXED_NOW)
    # status may be 'running' or 'orphan' depending on if PID 999999 exists
    # On most systems it doesn't; but the key invariant is age_seconds is small
    assert report["age_seconds"] == 5 * 60
    assert report["status"] in ("running", "orphan")


def test_running_stale_beyond_threshold(tmp_path):
    # last_update 40 hours ago — the actual incident
    last = _FIXED_NOW - timedelta(hours=40)
    p = _write_state(tmp_path, last_update=last.isoformat())
    report = check(p, threshold_seconds=2 * 3600, now=_FIXED_NOW)
    # PID 999999 fake → orphan takes priority over stale
    assert report["status"] in ("orphan", "stale")
    assert report["age_seconds"] >= 40 * 3600
    assert "investigate" in report["recommendation"] or "lock orphan" in report["recommendation"]


def test_orphan_detected_when_pid_dead(tmp_path):
    # PID 0 is never alive
    p = _write_state(tmp_path, pid="0", last_update="2026-04-24T11:59:00+00:00")
    report = check(p, threshold_seconds=2 * 3600, now=_FIXED_NOW)
    assert report["status"] == "orphan"
    assert report["pid_alive"] is False
    assert "lock orphan" in report["recommendation"]


def test_idle_status_honored_even_if_old(tmp_path):
    last = _FIXED_NOW - timedelta(days=10)
    p = _write_state(tmp_path, status="idle", last_update=last.isoformat())
    report = check(p, threshold_seconds=2 * 3600, now=_FIXED_NOW)
    assert report["status"] == "idle"
    assert report["recommendation"] == "honor declared non-running status"


def test_invalid_pid_handled(tmp_path):
    p = _write_state(tmp_path, pid="not-a-pid", last_update="2026-04-24T11:55:00+00:00")
    report = check(p, threshold_seconds=2 * 3600, now=_FIXED_NOW)
    # Should not crash; pid should be None
    assert report["pid"] is None


def test_z_suffix_timestamp_accepted(tmp_path):
    # Some daemons emit "Z" suffix instead of "+00:00"
    p = _write_state(tmp_path, last_update="2026-04-24T11:55:00Z")
    report = check(p, threshold_seconds=2 * 3600, now=_FIXED_NOW)
    assert report["age_seconds"] == 5 * 60
