#!/usr/bin/env python3
"""HEAD 指標 refresh — 防 header 漂白.

每輪 LOOP 第 0 步跑，拿真實數字，不靠 program.md header 記憶。連兩輪漂白
(v7.2-sensor + v7.3-sensor 實測 bare except / auto-commit 語意率 / fat-watch
三處 stale) 直接證明「靠人手算」是結構性漏洞。

指標涵蓋:
- bare_except: 總數 / 檔數 / top 10 熱點
- fat_files: ≥400 (red) / 350-399 (yellow) 邊界
- corpus: kb_data/corpus/**/*.md count (LIQG 擴量指標)
- log_lines: engineer-log / program.md / results.log 行數
- auto_commit_rate: 最近 30 commits 語意率 (T-COMMIT-SEMANTIC-GUARD 守門)
- epic6_progress: T-LIQG-x 進度 (從 openspec/changes/06-*/tasks.md 抓)

輸出:
- stdout: JSON (機器單一事實源)
- --human: stderr markdown 摘要
- exit code: 0=no hard violations / 1=soft violations only when --strict-soft / 2=hard violations
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Hard limits (超過 → exit 2)
_HARD_LIMITS = {
    "bare_except_total": 150,
    "engineer_log_lines": 400,
    "program_md_lines": 500,
    "fat_file_count_red": 8,  # > 400 行的檔數
    "pytest_cold_runtime_secs": 300.0,
}

# Soft limits (超過 → exit 1)
_SOFT_LIMITS = {
    "bare_except_total": 90,
    "engineer_log_lines": 300,
    "program_md_lines": 250,
    "corpus_count_min": 200,  # 低於 → soft violation
    # T7.5 (change 07): tighten from 0.20 → 0.90 for Auto-Dev Engineer authored
    # commits only. T-COMMIT-SEMANTIC-GUARD v3 mandates 90% semantic compliance
    # for the auto-engineer runtime once T7.1-T7.3 wire validate_auto_commit_msg
    # into the commit pipeline.
    "auto_commit_rate_min": 0.90,
    "pytest_cold_runtime_secs": 200.0,
}

# Author identity used by the auto-engineer runtime; sensor measures rate
# against this subset only (humans / pua-loop sessions are exempt because they
# already pass commit_msg_lint inline).
_AUTO_ENGINEER_AUTHOR_PATTERN = "Auto-Dev Engineer"


@dataclass
class SensorReport:
    bare_except_total: int = 0
    bare_except_files: int = 0
    bare_except_top: list[tuple[str, int]] = field(default_factory=list)
    fat_files_red: list[tuple[str, int]] = field(default_factory=list)
    fat_files_yellow: list[tuple[str, int]] = field(default_factory=list)
    fat_ratchet_ok: bool = True
    fat_ratchet_detail: str = ""
    corpus_count: int = 0
    engineer_log_lines: int = 0
    program_md_lines: int = 0
    results_log_lines: int = 0
    auto_commit_rate: float = 0.0
    auto_commit_recent_30_semantic: int = 0
    epic6_progress: tuple[int, int] = (0, 0)  # kept for backwards-compat; replaced by active_epic_progress
    active_epic_progress: dict = field(default_factory=lambda: {"epic_id": "", "done": 0, "total": 0})
    violations_hard: list[str] = field(default_factory=list)
    violations_soft: list[str] = field(default_factory=list)
    pytest_cold_runtime_secs: float = 0.0
    marked_done_uncommitted: dict = field(default_factory=lambda: {"count": 0, "slugs": []})

    def to_dict(self) -> dict[str, Any]:
        return {
            "bare_except": {
                "total": self.bare_except_total,
                "files": self.bare_except_files,
                "top10": self.bare_except_top,
            },
            "fat_files": {
                "red_over_400": self.fat_files_red,
                "yellow_350_to_400": self.fat_files_yellow,
                "ratchet_ok": self.fat_ratchet_ok,
                "ratchet_detail": self.fat_ratchet_detail,
            },
            "corpus_count": self.corpus_count,
            "log_lines": {
                "engineer_log": self.engineer_log_lines,
                "program_md": self.program_md_lines,
                "results_log": self.results_log_lines,
            },
            "auto_commit": {
                "rate_recent_30": self.auto_commit_rate,
                "semantic_count": self.auto_commit_recent_30_semantic,
            },
            "epic6_progress": {
                "done": self.epic6_progress[0],
                "total": self.epic6_progress[1],
            },
            "active_epic_progress": self.active_epic_progress,
            "violations": {
                "hard": self.violations_hard,
                "soft": self.violations_soft,
            },
            "pytest_cold_runtime_secs": self.pytest_cold_runtime_secs,
            "marked_done_uncommitted": self.marked_done_uncommitted,
        }


# 對齊 v7.2-sensor grep pattern 「except Exception|except:」
# 涵蓋: `except Exception:` / `except Exception as e:` / `except:` 三種
# 不含 `except ValueError:` 等精確 catch（不算 bare）
_BARE_EXCEPT_RE = re.compile(r"except\s+Exception\b|except\s*:")
_SEMANTIC_RE = re.compile(
    r"^(feat|fix|refactor|docs|chore|test|perf|style|build|ci|revert)"
    r"(?:\([^)]+\))?!?:\s+.{10,}"
)

# Pseudo-semantic auto-engineer noise — passes _SEMANTIC_RE but is NOT truly semantic.
# e.g. `chore(auto-engineer): checkpoint snapshot (2026-04-25 18:17:35 +0800) @ 18:19`
# e.g. `chore(auto-engineer): patch`
# e.g. `chore(copilot): batch round 17`
# e.g. `chore(auto-engineer): AUTO-RESCUE missing import`     (漂白第六型 admin rescue)
# e.g. `chore(auto-engineer): 54 files (restore corpus)`      (漂白第六型 bulk admin batch)
# Aligned with commit_msg_lint._REJECT_PATTERNS; excluded from semantic count.
_CHECKPOINT_NOISE_RE = re.compile(
    r"^chore\((?:auto-engineer|copilot)\):\s*"
    r"(?:checkpoint(?:\s+snapshot)?|patch|batch|AUTO-RESCUE|\d+\s*files)\b",
    re.IGNORECASE,
)


def count_bare_except(repo: Path) -> tuple[int, int, list[tuple[str, int]]]:
    """掃 src/ 下所有 .py 的 bare except 出現次數."""
    src = repo / "src"
    if not src.exists():
        return 0, 0, []
    per_file: Counter[str] = Counter()
    for py in src.rglob("*.py"):
        try:
            text = py.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        matches = _BARE_EXCEPT_RE.findall(text)
        if matches:
            rel = py.relative_to(repo).as_posix()
            per_file[rel] = len(matches)
    total = sum(per_file.values())
    files = len(per_file)
    top = per_file.most_common(10)
    return total, files, top


def scan_fat_files(repo: Path) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """列 src/ 下 ≥400 (red) 和 350-399 (yellow) 的 Python 檔."""
    src = repo / "src"
    if not src.exists():
        return [], []
    red: list[tuple[str, int]] = []
    yellow: list[tuple[str, int]] = []
    for py in src.rglob("*.py"):
        try:
            lines = len(py.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            continue
        rel = py.relative_to(repo).as_posix()
        if lines >= 400:
            red.append((rel, lines))
        elif 350 <= lines < 400:
            yellow.append((rel, lines))
    red.sort(key=lambda x: -x[1])
    yellow.sort(key=lambda x: -x[1])
    return red, yellow


def count_corpus(repo: Path) -> int:
    """kb_data/corpus/**/*.md 總數."""
    corpus = repo / "kb_data" / "corpus"
    if not corpus.exists():
        return 0
    return sum(1 for _ in corpus.rglob("*.md"))


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return 0


def auto_commit_rate(
    repo: Path,
    n: int = 30,
    author: str | None = None,
) -> tuple[int, float]:
    """最近 n commits 的 semantic 合規比率.

    Args:
        repo: 專案根
        n: 取樣 commit 數
        author: 若給, 用 ``git log --author=<pattern>`` 過濾（T7.5: Auto-Dev
            Engineer only）. 不給則統計全體 commits.
    """
    cmd = ["git", "-C", str(repo), "log", f"-{n}", "--format=%s"]
    if author:
        cmd.insert(-1, f"--author={author}")
    try:
        out = subprocess.check_output(cmd, encoding="utf-8", errors="replace")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return 0, 0.0
    subjects = [line for line in out.splitlines() if line.strip()]
    if not subjects:
        return 0, 0.0
    semantic = sum(
        1 for s in subjects
        if _SEMANTIC_RE.match(s) and not _CHECKPOINT_NOISE_RE.match(s)
    )
    return semantic, semantic / len(subjects)


def measure_cold_runtime(repo: Path) -> float:
    """Run pytest --collect-only and return wall-clock seconds (0.0 on failure).

    Uses --collect-only for a fast (~2-10s) cold-start proxy that tracks suite
    size without running tests.  Sufficient to detect runtime regressions early.
    """
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/", "--ignore=tests/integration",
        "--collect-only", "-q", "--tb=no", "--no-header",
    ]
    start = time.monotonic()
    try:
        subprocess.run(cmd, cwd=str(repo), check=False, capture_output=True)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"[sensor_refresh] pytest measurement failed: {exc}", file=sys.stderr)
        return 0.0
    return round(time.monotonic() - start, 2)


def save_runtime_baseline(repo: Path, secs: float) -> None:
    """Persist measured runtime to scripts/runtime_baseline.json.

    Implements ratchet-down for the floor baseline: only updates
    pytest_cold_runtime_secs when secs <= current baseline.

    Always updates last_measured_secs so sensor.json reports the real
    value, not the historical minimum.
    """
    path = repo / "scripts" / "runtime_baseline.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    try:
        data: dict = {}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    if secs > 0:
        # Always record the most recent measurement for display / up-creep detection.
        data["last_measured_secs"] = secs
        current = float(data.get("pytest_cold_runtime_secs", 0.0))
        if current <= 0 or secs <= current:
            data["pytest_cold_runtime_secs"] = secs
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError:
        return


def read_runtime_baseline(repo: Path) -> float:
    """Read the most recent runtime value from scripts/runtime_baseline.json.

    Prefers last_measured_secs (actual last run) over the floor baseline so
    sensor.json reflects reality rather than the historical minimum.
    Falls back to pytest_cold_runtime_secs for backwards compatibility.
    """
    path = repo / "scripts" / "runtime_baseline.json"
    if not path.exists():
        return 0.0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Prefer the most-recent real measurement if recorded.
        last = float(data.get("last_measured_secs", 0.0))
        if last > 0:
            return last
        return float(data.get("pytest_cold_runtime_secs", 0.0))
    except (OSError, json.JSONDecodeError, ValueError):
        return 0.0


def read_ceiling_params(repo: Path) -> tuple[float, float]:
    """Read ceiling_secs and tolerance_pct from scripts/runtime_baseline.json.

    Returns (ceiling_secs, tolerance_pct).  If not set, returns (0.0, 0.0)
    meaning ceiling check is disabled.
    """
    path = repo / "scripts" / "runtime_baseline.json"
    if not path.exists():
        return 0.0, 0.0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        ceiling = float(data.get("ceiling_secs", 0.0))
        tolerance = float(data.get("tolerance_pct", 0.0))
        return ceiling, tolerance
    except (OSError, json.JSONDecodeError, ValueError):
        return 0.0, 0.0


def epic6_progress(repo: Path) -> tuple[int, int]:
    """從 openspec/changes/06-*/tasks.md 數 [x] / 總 task."""
    tasks_files = list(repo.glob("openspec/changes/06-*/tasks.md"))
    if not tasks_files:
        return 0, 0
    done = 0
    total = 0
    for tf in tasks_files:
        try:
            text = tf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if re.match(r"\s*- \[[xX]\]", line):
                done += 1
                total += 1
            elif re.match(r"\s*- \[ \]", line):
                total += 1
    return done, total


def active_epic_progress(repo: Path) -> dict[str, Any]:
    """Find the first non-archive epic in openspec/changes/ and report [x]/total.

    Returns {"epic_id": str, "done": int, "total": int}.
    Fallback (no active epic): epic_id="" done=0 total=0.
    """
    changes_dir = repo / "openspec" / "changes"
    if not changes_dir.is_dir():
        return {"epic_id": "", "done": 0, "total": 0}
    # Sort for determinism; skip archive/ directory
    candidates = sorted(
        d for d in changes_dir.iterdir()
        if d.is_dir() and d.name != "archive"
    )
    if not candidates:
        return {"epic_id": "", "done": 0, "total": 0}
    epic_dir = candidates[0]
    tasks_file = epic_dir / "tasks.md"
    if not tasks_file.exists():
        return {"epic_id": epic_dir.name, "done": 0, "total": 0}
    try:
        text = tasks_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"epic_id": epic_dir.name, "done": 0, "total": 0}
    done = 0
    total = 0
    for line in text.splitlines():
        if re.match(r"\s*- \[[xX~]\]", line):
            if re.match(r"\s*- \[[xX]\]", line):
                done += 1
            total += 1
        elif re.match(r"\s*- \[ \]", line):
            total += 1
    return {"epic_id": epic_dir.name, "done": done, "total": total}


def count_marked_done_uncommitted(repo: Path, n_commits: int = 30) -> dict:
    """Check [x] task slugs in recent program.md sections not in last n commits.

    Only scans the first 4 P0/P1 section headers (≈ 2 batch rounds) to avoid
    flagging legacy/archive tasks that naturally fall outside the 30-commit window.

    Returns {"count": int, "slugs": list[str]}.
    """
    program_md = repo / "program.md"
    if not program_md.exists():
        return {"count": 0, "slugs": []}

    text = program_md.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    # Limit scan to most-recent 4 section headers (2 P0 + 2 P1 ≈ 2 batch rounds)
    section_header_re = re.compile(r"^###\s+P[01]")
    section_count = 0
    scan_lines: list[str] = []
    for line in lines:
        if section_header_re.match(line):
            section_count += 1
            if section_count > 4:
                break
        scan_lines.append(line)

    scan_text = "\n".join(scan_lines)
    slug_re = re.compile(r"-\s*\[x\]\s+\*\*([A-Z][A-Z0-9\-]+)\*\*")
    slugs = list(dict.fromkeys(slug_re.findall(scan_text)))

    if not slugs:
        return {"count": 0, "slugs": []}

    cmd = ["git", "-C", str(repo), "log", f"-{n_commits}", "--format=%B"]
    try:
        commit_log = subprocess.check_output(cmd, encoding="utf-8", errors="replace")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"count": 0, "slugs": []}

    uncommitted = [s for s in slugs if s not in commit_log]
    return {"count": len(uncommitted), "slugs": uncommitted}


def check_fat_ratchet(repo: Path, red: list[tuple[str, int]], yellow: list[tuple[str, int]]) -> tuple[bool, str]:
    """讀 scripts/fat_baseline.json，驗證 yellow ratchet 未退步.

    Returns (ok, detail_message).
    """
    baseline_path = repo / "scripts" / "fat_baseline.json"
    if not baseline_path.exists():
        return True, "no baseline (skip ratchet check)"
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return True, f"baseline unreadable ({exc}), skip"

    baseline_count = baseline.get("yellow_count_max", 0)
    baseline_max = baseline.get("yellow_max_lines", 0)
    cur_count = len(yellow)
    cur_max = yellow[0][1] if yellow else 0

    violations: list[str] = []
    if cur_count > baseline_count:
        violations.append(f"yellow count {cur_count} > baseline {baseline_count}")
    if baseline_max > 0 and cur_max > baseline_max:
        violations.append(f"yellow max_lines {cur_max} > baseline {baseline_max}")
    if red:
        violations.append(f"red files {len(red)} ≥ 400 lines")

    if violations:
        return False, "; ".join(violations)
    return True, f"ok (count={cur_count}/{baseline_count}, max_lines={cur_max}/{baseline_max})"


def build_report(repo: Path) -> SensorReport:
    r = SensorReport()
    r.bare_except_total, r.bare_except_files, r.bare_except_top = count_bare_except(repo)
    r.fat_files_red, r.fat_files_yellow = scan_fat_files(repo)
    r.fat_ratchet_ok, r.fat_ratchet_detail = check_fat_ratchet(repo, r.fat_files_red, r.fat_files_yellow)
    r.corpus_count = count_corpus(repo)
    r.engineer_log_lines = count_lines(repo / "engineer-log.md")
    r.program_md_lines = count_lines(repo / "program.md")
    r.results_log_lines = count_lines(repo / "results.log")
    # T7.5: 統計範圍限制為 Auto-Dev Engineer 作者 — 人類 / pua-loop session
    # 已在 commit time 過 lint, 不需 sensor 把它們算進來稀釋訊號.
    r.auto_commit_recent_30_semantic, r.auto_commit_rate = auto_commit_rate(
        repo, author=_AUTO_ENGINEER_AUTHOR_PATTERN
    )
    r.epic6_progress = epic6_progress(repo)
    r.active_epic_progress = active_epic_progress(repo)
    r.pytest_cold_runtime_secs = read_runtime_baseline(repo)
    r.marked_done_uncommitted = count_marked_done_uncommitted(repo)
    _ceiling, _tolerance = read_ceiling_params(repo)

    # Hard violations
    if r.bare_except_total > _HARD_LIMITS["bare_except_total"]:
        r.violations_hard.append(
            f"bare_except_total {r.bare_except_total} > {_HARD_LIMITS['bare_except_total']}"
        )
    if r.engineer_log_lines > _HARD_LIMITS["engineer_log_lines"]:
        r.violations_hard.append(
            f"engineer_log_lines {r.engineer_log_lines} > {_HARD_LIMITS['engineer_log_lines']} (hard cap)"
        )
    if r.program_md_lines > _HARD_LIMITS["program_md_lines"]:
        r.violations_hard.append(
            f"program_md_lines {r.program_md_lines} > {_HARD_LIMITS['program_md_lines']}"
        )
    if r.fat_files_red:
        r.violations_hard.append(
            f"fat_file_count_red {len(r.fat_files_red)} > {_HARD_LIMITS['fat_file_count_red']}"
        )
    if not r.fat_ratchet_ok:
        r.violations_hard.append(f"fat_ratchet: {r.fat_ratchet_detail}")

    # Soft violations (only if not already hard-flagged by total)
    if (
        r.bare_except_total > _SOFT_LIMITS["bare_except_total"]
        and r.bare_except_total <= _HARD_LIMITS["bare_except_total"]
    ):
        r.violations_soft.append(
            f"bare_except_total {r.bare_except_total} > soft {_SOFT_LIMITS['bare_except_total']}"
        )
    if (
        r.engineer_log_lines > _SOFT_LIMITS["engineer_log_lines"]
        and r.engineer_log_lines <= _HARD_LIMITS["engineer_log_lines"]
    ):
        r.violations_soft.append(
            f"engineer_log_lines {r.engineer_log_lines} > soft {_SOFT_LIMITS['engineer_log_lines']}"
        )
    if (
        r.program_md_lines > _SOFT_LIMITS["program_md_lines"]
        and r.program_md_lines <= _HARD_LIMITS["program_md_lines"]
    ):
        r.violations_soft.append(
            f"program_md_lines {r.program_md_lines} > soft {_SOFT_LIMITS['program_md_lines']}"
        )
    if r.corpus_count < _SOFT_LIMITS["corpus_count_min"] and r.corpus_count > 0:
        r.violations_soft.append(
            f"corpus_count {r.corpus_count} < target {_SOFT_LIMITS['corpus_count_min']}"
        )
    if (
        r.auto_commit_rate < _SOFT_LIMITS["auto_commit_rate_min"]
        and r.auto_commit_recent_30_semantic > 0
    ):
        r.violations_soft.append(
            f"auto_commit_rate {r.auto_commit_rate:.1%} < target {_SOFT_LIMITS['auto_commit_rate_min']:.0%}"
        )

    # Runtime ratchet (T-RUNTIME-RATCHET-SENSOR)
    if r.pytest_cold_runtime_secs > 0:
        if r.pytest_cold_runtime_secs > _HARD_LIMITS["pytest_cold_runtime_secs"]:
            r.violations_hard.append(
                f"pytest_cold_runtime_secs {r.pytest_cold_runtime_secs:.1f}s"
                f" > hard {_HARD_LIMITS['pytest_cold_runtime_secs']:.0f}s"
            )
        elif r.pytest_cold_runtime_secs > _SOFT_LIMITS["pytest_cold_runtime_secs"]:
            r.violations_soft.append(
                f"pytest_cold_runtime_secs {r.pytest_cold_runtime_secs:.1f}s"
                f" > soft {_SOFT_LIMITS['pytest_cold_runtime_secs']:.0f}s"
            )
        # Ceiling up-creep check (T-RUNTIME-BASELINE-TRUE-MEASURE-v3)
        # If ceiling_secs is configured, flag when runtime exceeds ceiling*(1+tolerance)
        elif _ceiling > 0 and r.pytest_cold_runtime_secs > _ceiling * (1 + _tolerance):
            r.violations_soft.append(
                f"pytest_cold_runtime_secs {r.pytest_cold_runtime_secs:.1f}s"
                f" > ceiling {_ceiling:.1f}s * (1+{_tolerance:.0%}) ="
                f" {_ceiling * (1 + _tolerance):.1f}s (up-creep)"
            )

    # marked_done_uncommitted ratchet (T-MARKED-DONE-COMMIT-RATCHET)
    mdu_count = r.marked_done_uncommitted.get("count", 0)
    if mdu_count > 5:
        r.violations_hard.append(
            f"marked_done_uncommitted {mdu_count} > hard 5"
            f" slugs={r.marked_done_uncommitted.get('slugs', [])}"
        )
    elif mdu_count > 0:
        r.violations_soft.append(
            f"marked_done_uncommitted {mdu_count} > soft 0"
            f" slugs={r.marked_done_uncommitted.get('slugs', [])}"
        )

    return r


def format_human(r: SensorReport) -> str:
    lines = [
        "# Sensor Refresh — HEAD 指標",
        "",
        f"- **bare_except**: {r.bare_except_total} 處 / {r.bare_except_files} 檔",
    ]
    if r.bare_except_top:
        lines.append("  - 熱點 top 5:")
        for path, n in r.bare_except_top[:5]:
            lines.append(f"    - {path}: {n}")

    lines.append(
        f"- **胖檔**: red (≥400) = {len(r.fat_files_red)} / yellow (350-399) = {len(r.fat_files_yellow)}"
        f" / ratchet={'✅' if r.fat_ratchet_ok else '🔴'} {r.fat_ratchet_detail}"
    )
    if r.fat_files_red:
        for path, n in r.fat_files_red[:5]:
            lines.append(f"    - 🔴 {path}: {n} 行")

    lines.append(f"- **corpus**: {r.corpus_count} 份 .md")
    lines.append(
        f"- **log 行數**: engineer-log {r.engineer_log_lines} / "
        f"program.md {r.program_md_lines} / results.log {r.results_log_lines}"
    )
    lines.append(
        f"- **auto-commit 語意率**: {r.auto_commit_rate:.1%} ({r.auto_commit_recent_30_semantic} / 近 30)"
    )
    if r.pytest_cold_runtime_secs > 0:
        lines.append(f"- **pytest cold runtime**: {r.pytest_cold_runtime_secs:.1f}s (soft≤200s / hard≤300s)")
    if r.marked_done_uncommitted.get("count", 0) > 0:
        lines.append(
            f"- **marked_done_uncommitted**: {r.marked_done_uncommitted['count']} slugs"
            f" = {r.marked_done_uncommitted['slugs']}"
        )
    if r.epic6_progress[1] > 0:
        lines.append(
            f"- **EPIC6 T-LIQG 進度**: {r.epic6_progress[0]}/{r.epic6_progress[1]}"
        )
    aep = r.active_epic_progress
    if aep.get("epic_id"):
        lines.append(
            f"- **active epic**: {aep['epic_id']} {aep['done']}/{aep['total']}"
        )

    if r.violations_hard:
        lines.append("")
        lines.append("## 🔴 HARD 違反")
        for v in r.violations_hard:
            lines.append(f"- {v}")
    if r.violations_soft:
        lines.append("")
        lines.append("## 🟡 SOFT 違反")
        for v in r.violations_soft:
            lines.append(f"- {v}")
    if not r.violations_hard and not r.violations_soft:
        lines.append("")
        lines.append("## ✅ 全部在目標內")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=_REPO_ROOT)
    parser.add_argument("--human", action="store_true", help="stderr 印 markdown 摘要")
    parser.add_argument(
        "--strict-soft",
        action="store_true",
        help="soft violations also return exit 1 (CI/nightly gate); default is hook-safe and only hard fails",
    )
    parser.add_argument(
        "--measure-runtime",
        action="store_true",
        help="(deprecated: measurement now runs by default via --collect-only)",
    )
    parser.add_argument(
        "--no-measure",
        action="store_true",
        help="skip automatic collection-time measurement (faster but no baseline update)",
    )
    args = parser.parse_args(argv)

    # T-RUNTIME-RATCHET-LIVE-MEASURE-v2: measurement is now the main path (not opt-in).
    # Uses --collect-only for a fast (~2-10s) cold-start proxy.  Skip with --no-measure.
    if not args.no_measure:
        secs = measure_cold_runtime(args.repo)
        if secs > 0:
            save_runtime_baseline(args.repo, secs)

    report = build_report(args.repo)
    print(json.dumps(report.to_dict(), ensure_ascii=False))
    if args.human:
        print(format_human(report), file=sys.stderr)

    if report.violations_hard:
        return 2
    if args.strict_soft and report.violations_soft:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
