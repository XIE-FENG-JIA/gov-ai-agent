#!/usr/bin/env python3
"""HEAD 指標 refresh — 防 header 漂白.

每輪 LOOP 第 0 步跑，拿真實數字，不靠 program.md header 記憶。連兩輪漂白
(v7.2-sensor + v7.3-sensor 實測 bare except / auto-commit 語意率 / fat-watch
三處 stale) 直接證明「靠人手算」是結構性漏洞。

指標涵蓋:
- bare_except: 總數 / 檔數 / top 10 熱點
- fat_files: >400 (red) / 350-400 (yellow) 邊界
- corpus: kb_data/corpus/**/*.md count (LIQG 擴量指標)
- log_lines: engineer-log / program.md / results.log 行數
- auto_commit_rate: 最近 30 commits 語意率 (T-COMMIT-SEMANTIC-GUARD 守門)
- epic6_progress: T-LIQG-x 進度 (從 openspec/changes/06-*/tasks.md 抓)

輸出:
- stdout: JSON (機器單一事實源)
- --human: stderr markdown 摘要
- exit code: 0=clean / 1=soft violations / 2=hard violations
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
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
}

# Soft limits (超過 → exit 1)
_SOFT_LIMITS = {
    "bare_except_total": 90,
    "engineer_log_lines": 300,
    "program_md_lines": 250,
    "corpus_count_min": 200,  # 低於 → soft violation
    "auto_commit_rate_min": 0.20,  # 低於 20% → soft violation
}


@dataclass
class SensorReport:
    bare_except_total: int = 0
    bare_except_files: int = 0
    bare_except_top: list[tuple[str, int]] = field(default_factory=list)
    fat_files_red: list[tuple[str, int]] = field(default_factory=list)
    fat_files_yellow: list[tuple[str, int]] = field(default_factory=list)
    corpus_count: int = 0
    engineer_log_lines: int = 0
    program_md_lines: int = 0
    results_log_lines: int = 0
    auto_commit_rate: float = 0.0
    auto_commit_recent_30_semantic: int = 0
    epic6_progress: tuple[int, int] = (0, 0)  # (done, total)
    violations_hard: list[str] = field(default_factory=list)
    violations_soft: list[str] = field(default_factory=list)

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
            "violations": {
                "hard": self.violations_hard,
                "soft": self.violations_soft,
            },
        }


# 對齊 v7.2-sensor grep pattern 「except Exception|except:」
# 涵蓋: `except Exception:` / `except Exception as e:` / `except:` 三種
# 不含 `except ValueError:` 等精確 catch（不算 bare）
_BARE_EXCEPT_RE = re.compile(r"except\s+Exception\b|except\s*:")
_SEMANTIC_RE = re.compile(
    r"^(feat|fix|refactor|docs|chore|test|perf|style|build|ci|revert)"
    r"(?:\([^)]+\))?!?:\s+.{10,}"
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
    """列 src/ 下超 400 (red) 和 350-400 (yellow) 的 Python 檔."""
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
        if lines > 400:
            red.append((rel, lines))
        elif 350 <= lines <= 400:
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


def auto_commit_rate(repo: Path, n: int = 30) -> tuple[int, float]:
    """最近 n commits 的 semantic 合規比率."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo), "log", f"-{n}", "--format=%s"],
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return 0, 0.0
    subjects = [line for line in out.splitlines() if line.strip()]
    if not subjects:
        return 0, 0.0
    semantic = sum(1 for s in subjects if _SEMANTIC_RE.match(s))
    return semantic, semantic / len(subjects)


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


def build_report(repo: Path) -> SensorReport:
    r = SensorReport()
    r.bare_except_total, r.bare_except_files, r.bare_except_top = count_bare_except(repo)
    r.fat_files_red, r.fat_files_yellow = scan_fat_files(repo)
    r.corpus_count = count_corpus(repo)
    r.engineer_log_lines = count_lines(repo / "engineer-log.md")
    r.program_md_lines = count_lines(repo / "program.md")
    r.results_log_lines = count_lines(repo / "results.log")
    r.auto_commit_recent_30_semantic, r.auto_commit_rate = auto_commit_rate(repo)
    r.epic6_progress = epic6_progress(repo)

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
    if len(r.fat_files_red) > _HARD_LIMITS["fat_file_count_red"]:
        r.violations_hard.append(
            f"fat_file_count_red {len(r.fat_files_red)} > {_HARD_LIMITS['fat_file_count_red']}"
        )

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
        f"- **胖檔**: red (>400) = {len(r.fat_files_red)} / yellow (350-400) = {len(r.fat_files_yellow)}"
    )
    if r.fat_files_red:
        for path, n in r.fat_files_red[:5]:
            lines.append(f"    - 🔴 {path}: {n} 行")

    lines.append(f"- **corpus**: {r.corpus_count} 份 .md")
    lines.append(
        f"- **log 行數**: engineer-log {r.engineer_log_lines} / program.md {r.program_md_lines} / results.log {r.results_log_lines}"
    )
    lines.append(
        f"- **auto-commit 語意率**: {r.auto_commit_rate:.1%} ({r.auto_commit_recent_30_semantic} / 近 30)"
    )
    if r.epic6_progress[1] > 0:
        lines.append(
            f"- **EPIC6 T-LIQG 進度**: {r.epic6_progress[0]}/{r.epic6_progress[1]}"
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
    args = parser.parse_args(argv)

    report = build_report(args.repo)
    print(json.dumps(report.to_dict(), ensure_ascii=False))
    if args.human:
        print(format_human(report), file=sys.stderr)

    if report.violations_hard:
        return 2
    if report.violations_soft:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
