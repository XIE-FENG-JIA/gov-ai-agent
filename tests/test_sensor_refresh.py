"""Tests for scripts/sensor_refresh.py."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "sensor_refresh.py"
_spec = importlib.util.spec_from_file_location("sensor_refresh", _MODULE_PATH)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["sensor_refresh"] = _mod  # register before exec_module (dataclass trick)
_spec.loader.exec_module(_mod)


def _make_repo(tmp_path: Path) -> Path:
    """Build minimal repo layout for sensor tests."""
    (tmp_path / "src").mkdir()
    (tmp_path / "kb_data" / "corpus" / "mohw").mkdir(parents=True)
    (tmp_path / "openspec" / "changes" / "06-live-ingest-quality-gate").mkdir(parents=True)
    return tmp_path


def test_bare_except_counts_exception_patterns(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    src = repo / "src"
    (src / "a.py").write_text(
        "def f():\n"
        "    try:\n        pass\n    except Exception:\n        pass\n"
        "    try:\n        pass\n    except:\n        pass\n",
        encoding="utf-8",
    )
    (src / "b.py").write_text(
        "def g():\n    try:\n        pass\n    except Exception as e:\n        pass\n",
        encoding="utf-8",
    )
    (src / "c.py").write_text("def h():\n    return 1\n", encoding="utf-8")

    total, files, top = _mod.count_bare_except(repo)
    assert total == 3  # 2 in a.py + 1 in b.py
    assert files == 2
    assert top[0][0] == "src/a.py"
    assert top[0][1] == 2


def test_scan_fat_files_red_vs_yellow(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    src = repo / "src"
    (src / "fat.py").write_text("\n".join(["x = 1"] * 400), encoding="utf-8")  # ≥400 red
    (src / "medium.py").write_text("\n".join(["x = 1"] * 399), encoding="utf-8")  # 350-399 yellow
    (src / "thin.py").write_text("\n".join(["x = 1"] * 100), encoding="utf-8")  # < 350

    red, yellow = _mod.scan_fat_files(repo)
    red_paths = [p for p, _ in red]
    yellow_paths = [p for p, _ in yellow]
    assert "src/fat.py" in red_paths
    assert "src/medium.py" in yellow_paths
    assert "src/thin.py" not in red_paths + yellow_paths


def test_count_corpus_glob_recursive(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    corpus = repo / "kb_data" / "corpus"
    (corpus / "mohw" / "a.md").write_text("# a", encoding="utf-8")
    (corpus / "mohw" / "b.md").write_text("# b", encoding="utf-8")
    (corpus / "mojlaw").mkdir()
    (corpus / "mojlaw" / "c.md").write_text("# c", encoding="utf-8")
    (corpus / "mojlaw" / "not_md.txt").write_text("ignore", encoding="utf-8")

    assert _mod.count_corpus(repo) == 3


def test_count_corpus_missing_dir(tmp_path: Path) -> None:
    # No kb_data at all
    assert _mod.count_corpus(tmp_path) == 0


def test_count_lines_basic(tmp_path: Path) -> None:
    p = tmp_path / "log.md"
    p.write_text("a\nb\nc\n", encoding="utf-8")
    assert _mod.count_lines(p) == 3
    assert _mod.count_lines(tmp_path / "missing.md") == 0


def test_auto_commit_rate_semantic_vs_checkpoint(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    # Set up a git repo with known commits
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@x"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)

    messages = [
        "feat(api): add route with long enough subject",
        "fix(cli): correct bug in argument parsing for long",
        "auto-commit: auto-engineer checkpoint (2026-04-25) @ now",
        "WIP",
        "docs(engineer-log): T9.6-REOPEN-v7 archive",
    ]
    for i, msg in enumerate(messages):
        (repo / f"f{i}.txt").write_text(str(i), encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", f"f{i}.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", msg, "-q"],
            check=True,
        )

    semantic, rate = _mod.auto_commit_rate(repo, n=5)
    # feat / fix / docs = 3 semantic; auto-commit checkpoint + WIP = 2 non-semantic
    assert semantic == 3
    assert rate == pytest.approx(0.6, abs=0.01)


def test_auto_commit_rate_filters_by_author(tmp_path: Path) -> None:
    """T7.5 — sensor 必須能只統計 Auto-Dev Engineer 作者的 commits."""
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "human@x"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Human Dev"], check=True)

    # 1 human semantic commit
    (repo / "h.txt").write_text("h", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "h.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "feat(api): human did this commit", "-q"],
        check=True,
    )

    # Switch identity to Auto-Dev Engineer for next 3 commits
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "engineer@auto-dev.local"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Auto-Dev Engineer"], check=True
    )

    auto_msgs = [
        "chore(auto-engineer): feat-add-foo @2026-04-25",  # semantic
        "auto-commit: auto-engineer checkpoint @2026-04-25",  # NOT semantic
        "chore(auto-engineer): docs-update-spec @2026-04-25",  # semantic
    ]
    for i, msg in enumerate(auto_msgs):
        (repo / f"a{i}.txt").write_text(str(i), encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", f"a{i}.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", msg, "-q"], check=True)

    # Without author filter: 4 commits, 3 semantic (human feat + 2 chore) = 75%
    sem_all, rate_all = _mod.auto_commit_rate(repo, n=10)
    assert sem_all == 3
    assert rate_all == pytest.approx(0.75, abs=0.01)

    # With author filter: 3 auto-engineer commits, 2 semantic = 66.7%
    sem_auto, rate_auto = _mod.auto_commit_rate(repo, n=10, author="Auto-Dev Engineer")
    assert sem_auto == 2
    assert rate_auto == pytest.approx(2 / 3, abs=0.01)


def test_soft_limit_auto_commit_rate_tightened_to_0_9() -> None:
    """T7.5 — _SOFT_LIMITS['auto_commit_rate_min'] must be 0.9 (was 0.20)."""
    assert _mod._SOFT_LIMITS["auto_commit_rate_min"] == pytest.approx(0.9)


def test_epic6_progress_counts_done_vs_total(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    tasks = repo / "openspec" / "changes" / "06-live-ingest-quality-gate" / "tasks.md"
    tasks.write_text(
        "# Tasks\n"
        "- [x] T-LIQG-1 quality gate contract\n"
        "- [x] T-LIQG-2 config\n"
        "- [ ] T-LIQG-3 CLI\n"
        "- [ ] T-LIQG-4 flag\n"
        "- [ ] T-LIQG-5 docs\n"
        "some unrelated text\n",
        encoding="utf-8",
    )
    done, total = _mod.epic6_progress(repo)
    assert done == 2
    assert total == 5


def test_active_epic_progress_no_active_epic(tmp_path: Path) -> None:
    """active_epic_progress returns fallback when no non-archive epic exists."""
    # Use tmp_path directly (not _make_repo) to control exactly what's in openspec/changes/
    archive = tmp_path / "openspec" / "changes" / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    result = _mod.active_epic_progress(tmp_path)
    assert result == {"epic_id": "", "done": 0, "total": 0}


def test_active_epic_progress_active_epic_statistics(tmp_path: Path) -> None:
    """active_epic_progress picks first non-archive dir and computes done/total."""
    # Use tmp_path directly to control exactly what's in openspec/changes/
    changes = tmp_path / "openspec" / "changes"
    (changes / "archive").mkdir(parents=True, exist_ok=True)
    epic_dir = changes / "19-kb-recall-validation-pipeline"
    epic_dir.mkdir(parents=True, exist_ok=True)
    (epic_dir / "tasks.md").write_text(
        "# Tasks\n"
        "- [x] T19.1 eval set\n"
        "- [x] T19.2 eval_recall.py\n"
        "- [ ] T19.3 CI gate\n"
        "- [ ] T19.4 docs\n",
        encoding="utf-8",
    )
    result = _mod.active_epic_progress(tmp_path)
    assert result["epic_id"] == "19-kb-recall-validation-pipeline"
    assert result["done"] == 2
    assert result["total"] == 4


def test_build_report_hard_violation_engineer_log(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    # engineer-log > hard cap 400
    (repo / "engineer-log.md").write_text("line\n" * 500, encoding="utf-8")
    (repo / "program.md").write_text("x\n" * 100, encoding="utf-8")
    r = _mod.build_report(repo)
    assert r.engineer_log_lines == 500
    assert any("engineer_log_lines 500" in v for v in r.violations_hard)


def test_build_report_soft_violation_engineer_log(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    # engineer-log 350: soft violated (>300) but < hard (400)
    (repo / "engineer-log.md").write_text("line\n" * 350, encoding="utf-8")
    (repo / "program.md").write_text("x\n" * 100, encoding="utf-8")
    r = _mod.build_report(repo)
    assert any("engineer_log_lines 350" in v for v in r.violations_soft)
    assert not any("engineer_log_lines" in v for v in r.violations_hard)


def test_main_exit_code_clean(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "engineer-log.md").write_text("x\n" * 100, encoding="utf-8")
    (repo / "program.md").write_text("x\n" * 100, encoding="utf-8")
    rc = _mod.main(["--repo", str(repo)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["log_lines"]["engineer_log"] == 100


def test_main_exit_2_hard(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "engineer-log.md").write_text("x\n" * 500, encoding="utf-8")
    (repo / "program.md").write_text("x\n" * 100, encoding="utf-8")
    rc = _mod.main(["--repo", str(repo)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["violations"]["hard"]


def test_main_soft_violations_are_hook_safe_by_default(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "engineer-log.md").write_text("x\n" * 350, encoding="utf-8")
    (repo / "program.md").write_text("x\n" * 100, encoding="utf-8")

    rc = _mod.main(["--repo", str(repo)])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["violations"]["soft"]
    assert not payload["violations"]["hard"]


def test_main_strict_soft_returns_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "engineer-log.md").write_text("x\n" * 350, encoding="utf-8")
    (repo / "program.md").write_text("x\n" * 100, encoding="utf-8")

    rc = _mod.main(["--repo", str(repo), "--strict-soft"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert payload["violations"]["soft"]
    assert not payload["violations"]["hard"]


def test_main_human_mode_prints_stderr(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "engineer-log.md").write_text("x\n" * 100, encoding="utf-8")
    (repo / "program.md").write_text("x\n" * 100, encoding="utf-8")
    _mod.main(["--repo", str(repo), "--human"])
    out = capsys.readouterr()
    assert "Sensor Refresh" in out.err
    # JSON still on stdout
    json.loads(out.out)


def test_auto_commit_rate_excludes_checkpoint_noise(tmp_path: Path) -> None:
    """T-AUTO-COMMIT-RATE-RECOMPUTE: chore(auto-engineer) checkpoint noise ≠ semantic."""
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@x"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)

    messages = [
        "feat(api): add endpoint for document export",  # semantic
        "chore(auto-engineer): checkpoint snapshot (2026-04-25 18:17:35 +0800) @ 18:19",  # noise
        "chore(auto-engineer): patch",  # noise
        "chore(copilot): batch round 17 (2026-04-26 00:02:55 +0800)",  # noise
        "chore(auto-engineer): feat-add-foo @2026-04-25",  # semantic (has real description)
        "fix(cli): correct argument parsing for long options list",  # semantic
    ]
    for i, msg in enumerate(messages):
        (repo / f"f{i}.txt").write_text(str(i), encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", f"f{i}.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", msg, "-q"], check=True)

    semantic, rate = _mod.auto_commit_rate(repo, n=6)
    # feat + chore(auto-engineer) real-desc + fix = 3; checkpoint noise excluded
    assert semantic == 3, f"expected 3 semantic, got {semantic}"
    assert rate == pytest.approx(0.50, abs=0.01)


# ── T-RUNTIME-RATCHET-SENSOR tests ──────────────────────────────────────────

def test_sensor_report_includes_pytest_cold_runtime(tmp_path: Path) -> None:
    """sensor to_dict() must expose pytest_cold_runtime_secs field (T-RUNTIME-RATCHET-SENSOR)."""
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "engineer-log.md").write_text("x\n" * 50, encoding="utf-8")
    (repo / "program.md").write_text("x\n" * 50, encoding="utf-8")
    # Write a runtime_baseline.json
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "runtime_baseline.json").write_text(
        '{"pytest_cold_runtime_secs": 42.5}', encoding="utf-8"
    )
    r = _mod.build_report(repo)
    assert r.pytest_cold_runtime_secs == pytest.approx(42.5)
    d = r.to_dict()
    assert "pytest_cold_runtime_secs" in d
    assert d["pytest_cold_runtime_secs"] == pytest.approx(42.5)


def test_sensor_hard_violation_when_runtime_exceeds_300s(tmp_path: Path) -> None:
    """Hard violation triggered when stored runtime > 300s (T-RUNTIME-RATCHET-SENSOR)."""
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "engineer-log.md").write_text("x\n" * 50, encoding="utf-8")
    (repo / "program.md").write_text("x\n" * 50, encoding="utf-8")
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "runtime_baseline.json").write_text(
        '{"pytest_cold_runtime_secs": 350.0}', encoding="utf-8"
    )
    r = _mod.build_report(repo)
    assert r.pytest_cold_runtime_secs == pytest.approx(350.0)
    assert any("pytest_cold_runtime_secs" in v for v in r.violations_hard), (
        f"Expected hard violation for 350s runtime; got hard={r.violations_hard}"
    )


def test_sensor_soft_violation_when_runtime_between_200_and_300s(tmp_path: Path) -> None:
    """Soft violation triggered when stored runtime in (200s, 300s] (T-RUNTIME-RATCHET-SENSOR)."""
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "engineer-log.md").write_text("x\n" * 50, encoding="utf-8")
    (repo / "program.md").write_text("x\n" * 50, encoding="utf-8")
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "runtime_baseline.json").write_text(
        '{"pytest_cold_runtime_secs": 250.0}', encoding="utf-8"
    )
    r = _mod.build_report(repo)
    assert r.pytest_cold_runtime_secs == pytest.approx(250.0)
    assert any("pytest_cold_runtime_secs" in v for v in r.violations_soft), (
        f"Expected soft violation for 250s runtime; got soft={r.violations_soft}"
    )
    assert not any("pytest_cold_runtime_secs" in v for v in r.violations_hard)


# ── T-RUNTIME-RATCHET-LIVE-MEASURE tests ──────────────────────────────────────

def test_save_runtime_baseline_writes_json(tmp_path: Path) -> None:
    """save_runtime_baseline writes pytest_cold_runtime_secs to scripts/runtime_baseline.json."""
    repo = tmp_path
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir()
    _mod.save_runtime_baseline(repo, 123.45)
    data = json.loads((scripts_dir / "runtime_baseline.json").read_text(encoding="utf-8"))
    assert data["pytest_cold_runtime_secs"] == pytest.approx(123.45)


def test_save_runtime_baseline_updates_existing(tmp_path: Path) -> None:
    """save_runtime_baseline updates an existing file when new value is smaller (ratchet-down)."""
    repo = tmp_path
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "runtime_baseline.json").write_text(
        '{"pytest_cold_runtime_secs": 50.0, "_note": "original"}', encoding="utf-8"
    )
    _mod.save_runtime_baseline(repo, 38.5)
    data = json.loads((scripts_dir / "runtime_baseline.json").read_text(encoding="utf-8"))
    assert data["pytest_cold_runtime_secs"] == pytest.approx(38.5)
    assert data.get("_note") == "original"


def test_save_runtime_baseline_ratchet_down_no_update(tmp_path: Path) -> None:
    """save_runtime_baseline must NOT update when new value exceeds current baseline."""
    repo = tmp_path
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "runtime_baseline.json").write_text(
        '{"pytest_cold_runtime_secs": 38.5}', encoding="utf-8"
    )
    _mod.save_runtime_baseline(repo, 87.6)
    data = json.loads((scripts_dir / "runtime_baseline.json").read_text(encoding="utf-8"))
    assert data["pytest_cold_runtime_secs"] == pytest.approx(38.5), (
        "ratchet-down: larger measured value must not replace smaller baseline"
    )


def test_measure_runtime_flag_updates_baseline(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Measurement runs by default (main path), writes baseline, and returns non-50.0."""
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "engineer-log.md").write_text("x\n" * 50, encoding="utf-8")
    (repo / "program.md").write_text("x\n" * 50, encoding="utf-8")
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "runtime_baseline.json").write_text(
        '{"pytest_cold_runtime_secs": 50.0}', encoding="utf-8"
    )
    (scripts_dir / "fat_baseline.json").write_text(
        '{"yellow_count_max": 0, "yellow_max_lines": 0}', encoding="utf-8"
    )

    # Monkeypatch measure_cold_runtime to avoid actually running pytest
    original = _mod.measure_cold_runtime
    try:
        _mod.measure_cold_runtime = lambda repo: 38.5
        # No --measure-runtime flag needed — measurement is now the main path
        rc = _mod.main(["--repo", str(repo)])
    finally:
        _mod.measure_cold_runtime = original

    assert rc == 0
    data = json.loads((scripts_dir / "runtime_baseline.json").read_text(encoding="utf-8"))
    assert data["pytest_cold_runtime_secs"] == pytest.approx(38.5), (
        "runtime_baseline.json should be updated with measured value (main path, not opt-in)"
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["pytest_cold_runtime_secs"] == pytest.approx(38.5)


def test_no_measure_flag_skips_measurement(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """--no-measure skips measurement and preserves existing baseline."""
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "engineer-log.md").write_text("x\n" * 50, encoding="utf-8")
    (repo / "program.md").write_text("x\n" * 50, encoding="utf-8")
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "runtime_baseline.json").write_text(
        '{"pytest_cold_runtime_secs": 42.0}', encoding="utf-8"
    )
    (scripts_dir / "fat_baseline.json").write_text(
        '{"yellow_count_max": 0, "yellow_max_lines": 0}', encoding="utf-8"
    )

    original = _mod.measure_cold_runtime
    called = []
    try:
        _mod.measure_cold_runtime = lambda repo: called.append(1) or 10.0
        rc = _mod.main(["--repo", str(repo), "--no-measure"])
    finally:
        _mod.measure_cold_runtime = original

    assert called == [], "--no-measure must skip measurement"
    data = json.loads((scripts_dir / "runtime_baseline.json").read_text(encoding="utf-8"))
    assert data["pytest_cold_runtime_secs"] == pytest.approx(42.0)


# ── T-RUNTIME-BASELINE-TRUE-MEASURE-v3 tests (ceiling / up-creep) ───────────


def test_ceiling_violation_triggers_soft(tmp_path: Path) -> None:
    """Soft violation when last_measured_secs > ceiling_secs * (1+tolerance_pct)."""
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "engineer-log.md").write_text("x\n" * 50, encoding="utf-8")
    (repo / "program.md").write_text("x\n" * 50, encoding="utf-8")
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir()
    # ceiling=50s, tolerance=10% → threshold=55s; measured=70s → soft
    (scripts_dir / "runtime_baseline.json").write_text(
        json.dumps({
            "pytest_cold_runtime_secs": 45.0,
            "last_measured_secs": 70.0,
            "ceiling_secs": 50.0,
            "tolerance_pct": 0.10,
        }),
        encoding="utf-8",
    )
    r = _mod.build_report(repo)
    assert r.pytest_cold_runtime_secs == pytest.approx(70.0), (
        "last_measured_secs should be reported, not floor baseline"
    )
    assert any("up-creep" in v for v in r.violations_soft), (
        f"Expected up-creep soft violation; got soft={r.violations_soft}"
    )
    assert not any("up-creep" in v for v in r.violations_hard)


def test_ceiling_no_violation_within_tolerance(tmp_path: Path) -> None:
    """No ceiling violation when last_measured_secs <= ceiling_secs * (1+tolerance_pct)."""
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "engineer-log.md").write_text("x\n" * 50, encoding="utf-8")
    (repo / "program.md").write_text("x\n" * 50, encoding="utf-8")
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir()
    # ceiling=80s, tolerance=20% → threshold=96s; measured=90s → ok
    (scripts_dir / "runtime_baseline.json").write_text(
        json.dumps({
            "pytest_cold_runtime_secs": 80.0,
            "last_measured_secs": 90.0,
            "ceiling_secs": 80.0,
            "tolerance_pct": 0.20,
        }),
        encoding="utf-8",
    )
    r = _mod.build_report(repo)
    assert r.pytest_cold_runtime_secs == pytest.approx(90.0)
    assert not any("up-creep" in v for v in r.violations_soft + r.violations_hard), (
        f"No up-creep violation expected for 90s ≤ 96s threshold; "
        f"soft={r.violations_soft} hard={r.violations_hard}"
    )


# ── T-MARKED-DONE-COMMIT-RATCHET tests ──────────────────────────────────────


def _git_commit(repo: Path, filename: str, content: str, message: str) -> None:
    (repo / filename).write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", filename], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", message, "-q"], check=True)


def test_marked_done_uncommitted_no_program_md(tmp_path: Path) -> None:
    """Returns zero violations when program.md does not exist."""
    result = _mod.count_marked_done_uncommitted(tmp_path)
    assert result == {"count": 0, "slugs": []}


def test_marked_done_uncommitted_slug_in_commits(tmp_path: Path) -> None:
    """[x] slug that appears in last-30 commits is NOT a violation."""
    repo = tmp_path
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@x"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    program_text = "### P0（2026-04-26 test batch）\n- [x] **T-FOO-BAR**\n"
    _git_commit(repo, "program.md", program_text, "docs(program): T-FOO-BAR done")
    result = _mod.count_marked_done_uncommitted(repo)
    assert result["count"] == 0


def test_marked_done_uncommitted_slug_not_in_commits(tmp_path: Path) -> None:
    """[x] slug NOT in any last-30 commit is a violation."""
    repo = tmp_path
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@x"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    program_text = "### P0（2026-04-26 test batch）\n- [x] **T-NEVER-COMMITTED**\n"
    _git_commit(repo, "program.md", program_text, "chore: unrelated work only")
    result = _mod.count_marked_done_uncommitted(repo)
    assert result["count"] == 1
    assert "T-NEVER-COMMITTED" in result["slugs"]


def test_marked_done_uncommitted_mixed(tmp_path: Path) -> None:
    """Correctly counts only slugs missing from commits when some are present."""
    repo = tmp_path
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@x"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    program_text = (
        "### P0（2026-04-26 test batch）\n"
        "- [x] **T-COMMITTED-ONE**\n"
        "- [x] **T-MISSING-TWO**\n"
        "- [ ] **T-OPEN-THREE**\n"
    )
    _git_commit(repo, "program.md", program_text, "feat: T-COMMITTED-ONE landed")
    result = _mod.count_marked_done_uncommitted(repo)
    assert result["count"] == 1
    assert "T-MISSING-TWO" in result["slugs"]
    assert "T-COMMITTED-ONE" not in result["slugs"]
    assert "T-OPEN-THREE" not in result["slugs"]


def test_marked_done_uncommitted_sections_beyond_4_excluded(tmp_path: Path) -> None:
    """Slugs from undated (archive/legacy) P0/P1 sections are excluded."""
    repo = tmp_path
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@x"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    program_text = (
        "### P0（2026-04-27 batch 5）\n"
        "- [x] **T-SLUG-IN-BATCH5**\n"
        "### P1（2026-04-27 batch 5）\n"
        "- [x] **T-SLUG-IN-P1-BATCH5**\n"
        "### P0（2026-04-26 batch 4）\n"
        "- [x] **T-SLUG-IN-BATCH4**\n"
        "### P1（2026-04-26 batch 4）\n"
        "- [x] **T-SLUG-IN-P1-BATCH4**\n"
        "### P0（batch 3 archive）\n"
        "- [x] **T-ARCHIVE-SLUG**\n"
    )
    _git_commit(repo, "program.md", program_text, "chore: none of the slugs committed here")
    result = _mod.count_marked_done_uncommitted(repo)
    slugs = result["slugs"]
    assert "T-ARCHIVE-SLUG" not in slugs, "undated archive section slug must be excluded"
    assert "T-SLUG-IN-BATCH5" in slugs
    assert "T-SLUG-IN-BATCH4" in slugs


def test_build_report_marked_done_uncommitted_in_dict(tmp_path: Path) -> None:
    """build_report includes marked_done_uncommitted in to_dict() output."""
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "engineer-log.md").write_text("x\n" * 50, encoding="utf-8")
    program_text = "### P0（2026-04-26 test）\n- [x] **T-UNMARKED-TEST**\n"
    _git_commit(repo, "program.md", program_text, "chore: unrelated commit only")
    r = _mod.build_report(repo)
    d = r.to_dict()
    assert "marked_done_uncommitted" in d
    assert isinstance(d["marked_done_uncommitted"]["count"], int)
    assert isinstance(d["marked_done_uncommitted"]["slugs"], list)


def test_build_report_soft_violation_marked_done_gt_0(tmp_path: Path) -> None:
    """Soft violation triggered when marked_done_uncommitted count > 0."""
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "engineer-log.md").write_text("x\n" * 50, encoding="utf-8")
    program_text = "### P0（2026-04-26 test）\n- [x] **T-SOFT-VIOL-SLUG**\n"
    _git_commit(repo, "program.md", program_text, "chore: unrelated")
    r = _mod.build_report(repo)
    assert any("marked_done_uncommitted" in v for v in r.violations_soft), (
        f"Expected soft violation; got soft={r.violations_soft}"
    )
    assert not any("marked_done_uncommitted" in v for v in r.violations_hard)


def test_build_report_hard_violation_marked_done_gt_5(tmp_path: Path) -> None:
    """Hard violation triggered when marked_done_uncommitted count > 5."""
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "engineer-log.md").write_text("x\n" * 50, encoding="utf-8")
    sluglines = "".join(f"- [x] **T-HARD-SLUG-{i}**\n" for i in range(6))
    program_text = f"### P0（2026-04-26 test）\n{sluglines}"
    _git_commit(repo, "program.md", program_text, "chore: unrelated only")
    r = _mod.build_report(repo)
    assert any("marked_done_uncommitted" in v for v in r.violations_hard), (
        f"Expected hard violation for 6 slugs; got hard={r.violations_hard}"
    )


# ── T22.4 — Adapter health sensor violation wiring ───────────────────────────

def _make_adapter_report(tmp_path: Path, adapters: list) -> Path:
    """Write a mock adapter_health_report.json and return the repo path."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "adapters": adapters,
        "measured_at": "2026-04-27T00:00:00+00:00",
        "dry_run": False,
    }
    path = scripts_dir / "adapter_health_report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return tmp_path


def test_check_adapter_health_ok_when_all_adapters_return_records(tmp_path: Path) -> None:
    """check_adapter_health returns status='ok' when all adapters have count>0."""
    repo = _make_adapter_report(tmp_path, [
        {"adapter": "mojlaw", "status": "ok", "latency_ms": 100, "count": 3, "error": None},
        {"adapter": "fda_api", "status": "ok", "latency_ms": 80, "count": 2, "error": None},
    ])
    result = _mod.check_adapter_health(repo)
    assert result["status"] == "ok"


def test_check_adapter_health_violation_when_adapter_count_zero(tmp_path: Path) -> None:
    """check_adapter_health returns status='violation' when adapter count==0."""
    repo = _make_adapter_report(tmp_path, [
        {"adapter": "mojlaw", "status": "ok", "latency_ms": 100, "count": 3, "error": None},
        {"adapter": "fda_api", "status": "zero_records", "latency_ms": 50, "count": 0, "error": None},
    ])
    result = _mod.check_adapter_health(repo)
    assert result["status"] == "violation"
    assert "fda_api" in result.get("detail", "")


def test_check_adapter_health_violation_when_adapter_error(tmp_path: Path) -> None:
    """check_adapter_health returns status='violation' when adapter status==error."""
    repo = _make_adapter_report(tmp_path, [
        {"adapter": "mohw_rss", "status": "error", "latency_ms": 10, "count": 0, "error": "timeout"},
    ])
    result = _mod.check_adapter_health(repo)
    assert result["status"] == "violation"


def test_check_adapter_health_skip_when_no_report(tmp_path: Path) -> None:
    """check_adapter_health returns status='skip' when report file is absent."""
    result = _mod.check_adapter_health(tmp_path)
    assert result["status"] == "skip"


def test_build_report_soft_violation_on_adapter_health_stall(tmp_path: Path) -> None:
    """build_report fires soft violation when adapter_health status == 'violation'."""
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "engineer-log.md").write_text("x\n" * 50, encoding="utf-8")
    (repo / "program.md").write_text("x\n" * 50, encoding="utf-8")
    # Write a report with a zero-count adapter
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "adapters": [
            {"adapter": "mojlaw", "status": "zero_records", "latency_ms": 10, "count": 0, "error": None},
        ],
        "measured_at": "2026-04-27T00:00:00+00:00",
        "dry_run": False,
    }
    (scripts_dir / "adapter_health_report.json").write_text(json.dumps(report), encoding="utf-8")
    r = _mod.build_report(repo)
    assert any("adapter-health-stall" in v for v in r.violations_soft), (
        f"Expected adapter-health-stall soft violation; got soft={r.violations_soft}"
    )


def test_sensor_report_includes_adapter_health_field(tmp_path: Path) -> None:
    """to_dict() includes adapter_health key with status field."""
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "engineer-log.md").write_text("x\n" * 50, encoding="utf-8")
    (repo / "program.md").write_text("x\n" * 50, encoding="utf-8")
    r = _mod.build_report(repo)
    d = r.to_dict()
    assert "adapter_health" in d
    assert "status" in d["adapter_health"]


# ---------------------------------------------------------------------------
# check_discord_push (T28.4)
# ---------------------------------------------------------------------------

def test_check_discord_push_both_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Returns token_set=True, channel_set=True when both env vars present."""
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "tok123")
    monkeypatch.setenv("DISCORD_ALERT_CHANNEL_ID", "chan456")
    result = _mod.check_discord_push()
    assert result == {"token_set": True, "channel_set": True}


def test_check_discord_push_none_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Returns token_set=False, channel_set=False when vars are absent."""
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_ALERT_CHANNEL_ID", raising=False)
    result = _mod.check_discord_push()
    assert result == {"token_set": False, "channel_set": False}


def test_check_discord_push_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only token set → channel_set=False."""
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "tok")
    monkeypatch.delenv("DISCORD_ALERT_CHANNEL_ID", raising=False)
    result = _mod.check_discord_push()
    assert result["token_set"] is True
    assert result["channel_set"] is False


def test_sensor_report_includes_discord_push_field(tmp_path: Path) -> None:
    """to_dict() includes discord_push key with token_set and channel_set."""
    repo = _make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "engineer-log.md").write_text("x\n" * 50, encoding="utf-8")
    (repo / "program.md").write_text("x\n" * 50, encoding="utf-8")
    r = _mod.build_report(repo)
    d = r.to_dict()
    assert "discord_push" in d
    assert "token_set" in d["discord_push"]
    assert "channel_set" in d["discord_push"]
