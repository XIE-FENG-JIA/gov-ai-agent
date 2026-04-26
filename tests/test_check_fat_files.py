"""Tests for scripts/check_fat_files.py."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "check_fat_files.py"
_spec = importlib.util.spec_from_file_location("check_fat_files", _MODULE_PATH)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["check_fat_files"] = _mod
_spec.loader.exec_module(_mod)


def _make_repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    return tmp_path


def test_scan_fat_files_treats_400_lines_as_red(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "src" / "red.py").write_text("x = 1\n" * 400, encoding="utf-8")
    (repo / "src" / "yellow.py").write_text("x = 1\n" * 399, encoding="utf-8")

    red, yellow = _mod.scan_fat_files(repo)

    assert red == [("src/red.py", 400)]
    assert yellow == [("src/yellow.py", 399)]


def test_build_report_fails_on_any_red_file(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "src" / "red.py").write_text("x = 1\n" * 400, encoding="utf-8")

    report = _mod.build_report(repo, {"yellow_count_max": 0, "yellow_max_lines": 0}, strict=True)

    assert report["red"] == [{"path": "src/red.py", "lines": 400}]
    assert any("RED src/red.py" in violation for violation in report["violations"])


def test_build_report_strict_fails_when_yellow_count_grows(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "src" / "yellow.py").write_text("x = 1\n" * 350, encoding="utf-8")

    report = _mod.build_report(repo, {"yellow_count_max": 0, "yellow_max_lines": 0}, strict=True)

    assert any("yellow count 1 > baseline 0" in violation for violation in report["violations"])


def test_build_report_non_strict_allows_yellow_growth(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "src" / "yellow.py").write_text("x = 1\n" * 350, encoding="utf-8")

    report = _mod.build_report(repo, {"yellow_count_max": 0, "yellow_max_lines": 0}, strict=False)

    assert report["violations"] == []


def test_parse_watch_band_accepts_inclusive_range() -> None:
    assert _mod.parse_watch_band("300-350") == (300, 350)


def test_build_report_watch_band_lists_files_without_violations(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "src" / "watched.py").write_text("x = 1\n" * 340, encoding="utf-8")
    (repo / "src" / "small.py").write_text("x = 1\n" * 299, encoding="utf-8")

    report = _mod.build_report(
        repo,
        {"yellow_count_max": 0, "yellow_max_lines": 0},
        strict=False,
        watch_band=(300, 350),
    )

    assert report["watch_band"] == {"low": 300, "high": 350}
    assert report["watch"] == [{"path": "src/watched.py", "lines": 340}]
    assert report["violations"] == []
