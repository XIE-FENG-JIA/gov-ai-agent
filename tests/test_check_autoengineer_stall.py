"""Tests for scripts/check_autoengineer_stall.py."""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parent.parent
    / "scripts"
    / "check_autoengineer_stall.py"
)
_spec = importlib.util.spec_from_file_location("check_autoengineer_stall", _MODULE_PATH)
assert _spec and _spec.loader
_stall_mod = importlib.util.module_from_spec(_spec)
# Register before exec so @dataclass can resolve cls.__module__ in sys.modules
sys.modules["check_autoengineer_stall"] = _stall_mod
_spec.loader.exec_module(_stall_mod)
check = _stall_mod.check
main = _stall_mod.main
_EXIT_CODE = _stall_mod._EXIT_CODE


def _write_state(tmp: Path, **overrides: object) -> Path:
    state = {
        "round": "120",
        "last_update": "2026-04-22T13:34:22+08:00",
        "status": "running",
    }
    state.update(overrides)
    path = tmp / ".auto-engineer.state.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return path


def test_ok_recent_last_update(tmp_path: Path) -> None:
    now = datetime(2026, 4, 24, 16, 30, tzinfo=timezone.utc)
    recent = (now - timedelta(minutes=10)).isoformat()
    state = _write_state(tmp_path, last_update=recent)
    report = check(state, threshold_hours=2.0, now=now)
    assert report.status == "OK"
    assert report.age_seconds is not None and report.age_seconds < 3600
    assert _EXIT_CODE[report.status] == 0


def test_stalled_old_last_update(tmp_path: Path) -> None:
    now = datetime(2026, 4, 24, 16, 30, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=51)).isoformat()
    state = _write_state(tmp_path, last_update=stale)
    report = check(state, threshold_hours=2.0, now=now)
    assert report.status == "STALLED"
    assert "51" in report.reason or "51.0h" in report.reason
    assert _EXIT_CODE[report.status] == 1


def test_future_last_update_flagged(tmp_path: Path) -> None:
    now = datetime(2026, 4, 24, 16, 30, tzinfo=timezone.utc)
    future = (now + timedelta(hours=3)).isoformat()
    state = _write_state(tmp_path, last_update=future)
    report = check(state, threshold_hours=2.0, now=now)
    assert report.status == "FUTURE"
    assert _EXIT_CODE[report.status] == 1


def test_missing_state_file(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.json"
    report = check(missing, threshold_hours=2.0)
    assert report.status == "MISSING"
    assert report.age_seconds is None
    assert _EXIT_CODE[report.status] == 2


def test_corrupt_json(tmp_path: Path) -> None:
    path = tmp_path / ".auto-engineer.state.json"
    path.write_text("{not valid json", encoding="utf-8")
    report = check(path, threshold_hours=2.0)
    assert report.status == "CORRUPT"
    assert _EXIT_CODE[report.status] == 2


def test_missing_last_update_key(tmp_path: Path) -> None:
    path = tmp_path / ".auto-engineer.state.json"
    path.write_text(json.dumps({"round": "1"}), encoding="utf-8")
    report = check(path, threshold_hours=2.0)
    assert report.status == "CORRUPT"
    assert "last_update" in report.reason


def test_bad_iso_timestamp(tmp_path: Path) -> None:
    state = _write_state(tmp_path, last_update="not a timestamp")
    report = check(state, threshold_hours=2.0)
    assert report.status == "CORRUPT"
    assert "ISO" in report.reason or "not ISO" in report.reason


def test_threshold_configurable(tmp_path: Path) -> None:
    now = datetime(2026, 4, 24, 16, 30, tzinfo=timezone.utc)
    ts = (now - timedelta(hours=3)).isoformat()
    state = _write_state(tmp_path, last_update=ts)
    # 2h threshold → stalled
    assert check(state, threshold_hours=2.0, now=now).status == "STALLED"
    # 4h threshold → ok
    assert check(state, threshold_hours=4.0, now=now).status == "OK"


def test_main_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    state = _write_state(
        tmp_path,
        last_update=datetime.now(timezone.utc).isoformat(),
    )
    rc = main(["--state", str(state), "--threshold-hours", "2"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["status"] == "OK"
    assert payload["round"] == "120"
    assert payload["threshold_hours"] == 2.0


def test_main_stalled_exit_code(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    stale = (datetime.now(timezone.utc) - timedelta(hours=51)).isoformat()
    state = _write_state(tmp_path, last_update=stale)
    rc = main(["--state", str(state), "--threshold-hours", "2"])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "STALLED"


def test_main_missing_exit_code(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--state", str(tmp_path / "nope.json")])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "MISSING"


def test_main_human_mode_uses_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state = _write_state(
        tmp_path, last_update=datetime.now(timezone.utc).isoformat()
    )
    rc = main(["--state", str(state), "--human"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "auto-engineer stall check" in captured.err
    # Human mode still emits JSON to stdout (so programs can parse) + human stderr
    payload = json.loads(captured.out)
    assert payload["status"] == "OK"
