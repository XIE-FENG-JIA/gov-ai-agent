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
    (src / "fat.py").write_text("\n".join(["x = 1"] * 450), encoding="utf-8")  # > 400 red
    (src / "medium.py").write_text("\n".join(["x = 1"] * 380), encoding="utf-8")  # 350-400 yellow
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
