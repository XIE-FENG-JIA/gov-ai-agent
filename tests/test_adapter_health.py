"""Unit tests for scripts/adapter_health.py (T22.3).

All tests mock adapter calls — no live network calls are made.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "adapter_health.py"
_spec = importlib.util.spec_from_file_location("adapter_health", _MODULE_PATH)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["adapter_health"] = _mod
_spec.loader.exec_module(_mod)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_probe(tmp_path: Path) -> "_mod.AdapterHealthProbe":  # type: ignore[name-defined]
    return _mod.AdapterHealthProbe(report_path=tmp_path / "adapter_health_report.json")


# ── T22.3 tests ───────────────────────────────────────────────────────────────


def test_dry_run_writes_report_with_all_adapters(tmp_path: Path) -> None:
    """dry-run produces a report with one entry per registered adapter."""
    probe = _make_probe(tmp_path)
    report = probe.run(dry_run=True)

    # Report file should be written
    assert (tmp_path / "adapter_health_report.json").exists()

    # Should have exactly as many adapters as the registry
    adapters = report["adapters"]
    assert len(adapters) == len(_mod._ADAPTER_REGISTRY)

    # All entries should have required keys
    for entry in adapters:
        assert "adapter" in entry
        assert "status" in entry
        assert "latency_ms" in entry
        assert "count" in entry

    # dry_run flag should be True in the report
    assert report["dry_run"] is True


def test_mock_adapter_zero_records_yields_zero_records_status(tmp_path: Path) -> None:
    """Adapter returning empty list → status 'zero_records'."""
    probe = _make_probe(tmp_path)

    # Patch _ADAPTER_REGISTRY to single mock adapter
    mock_cls = MagicMock()
    mock_cls.return_value.list.return_value = []

    with patch.object(_mod, "_ADAPTER_REGISTRY", [("test_zero", "some.module", "SomeClass")]):
        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_module.SomeClass = mock_cls
            mock_import.return_value = mock_module

            report = probe.run(dry_run=False)

    entries = report["adapters"]
    assert len(entries) == 1
    assert entries[0]["status"] == "zero_records"
    assert entries[0]["count"] == 0


def test_mock_adapter_raising_exception_yields_error_status(tmp_path: Path) -> None:
    """Adapter raising an exception → status 'error' with error string."""
    probe = _make_probe(tmp_path)

    mock_cls = MagicMock()
    mock_cls.return_value.list.side_effect = ConnectionError("network down")

    with patch.object(_mod, "_ADAPTER_REGISTRY", [("test_err", "some.module", "SomeClass")]):
        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_module.SomeClass = mock_cls
            mock_import.return_value = mock_module

            report = probe.run(dry_run=False)

    entries = report["adapters"]
    assert len(entries) == 1
    assert entries[0]["status"] == "error"
    assert entries[0]["count"] == 0
    assert "network down" in (entries[0]["error"] or "")


def test_mock_adapter_returning_three_records_yields_ok_status(tmp_path: Path) -> None:
    """Adapter returning 3 records → status 'ok', count == 3."""
    probe = _make_probe(tmp_path)

    mock_cls = MagicMock()
    mock_cls.return_value.list.return_value = [{"id": i} for i in range(3)]

    with patch.object(_mod, "_ADAPTER_REGISTRY", [("test_ok", "some.module", "SomeClass")]):
        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_module.SomeClass = mock_cls
            mock_import.return_value = mock_module

            report = probe.run(dry_run=False)

    entries = report["adapters"]
    assert len(entries) == 1
    assert entries[0]["status"] == "ok"
    assert entries[0]["count"] == 3


def test_human_output_contains_adapter_name_and_count(tmp_path: Path) -> None:
    """format_human() includes adapter name and count in the output."""
    report = {
        "adapters": [
            {"adapter": "mojlaw", "status": "ok", "latency_ms": 123, "count": 3, "error": None},
            {"adapter": "fda_api", "status": "zero_records", "latency_ms": 50, "count": 0, "error": None},
        ],
        "measured_at": "2026-04-27T00:00:00+00:00",
        "dry_run": False,
    }
    output = _mod.format_human(report)
    assert "mojlaw" in output
    assert "fda_api" in output
    assert "count=3" in output
    assert "count=0" in output


def test_human_output_shows_icons(tmp_path: Path) -> None:
    """format_human() shows [OK] for ok, [!] for zero_records, [X] for error."""
    report = {
        "adapters": [
            {"adapter": "a_ok", "status": "ok", "latency_ms": 10, "count": 1, "error": None},
            {"adapter": "a_zero", "status": "zero_records", "latency_ms": 5, "count": 0, "error": None},
            {"adapter": "a_err", "status": "error", "latency_ms": 8, "count": 0, "error": "timeout"},
        ],
        "measured_at": "2026-04-27T00:00:00+00:00",
        "dry_run": False,
    }
    output = _mod.format_human(report)
    assert "[OK]" in output
    assert "[!]" in output
    assert "[X]" in output


def test_dry_run_exits_0(tmp_path: Path) -> None:
    """main(['--dry-run', '--report', str(tmp_path/...)]) exits 0 and writes file."""
    report_path = tmp_path / "test_report.json"
    rc = _mod.main(["--dry-run", "--report", str(report_path)])
    assert rc == 0
    assert report_path.exists()
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert "adapters" in data
    assert data["dry_run"] is True


def test_dry_run_status_is_dry_run_only(tmp_path: Path) -> None:
    """dry-run mode reports status='dry_run_only' (≠ 'ok') for all adapters (T-ADAPTER-HEALTH-DRY-RUN-PATCH)."""
    probe = _make_probe(tmp_path)
    report = probe.run(dry_run=True)
    for entry in report["adapters"]:
        assert entry["status"] == "dry_run_only", (
            f"Expected 'dry_run_only' but got {entry['status']!r} for adapter {entry['adapter']!r}"
        )
