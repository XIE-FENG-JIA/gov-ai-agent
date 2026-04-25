"""Squash consecutive auto-commit checkpoint messages within time windows.

T-COMMIT-NOISE-FLOOR (b): Groups checkpoint commits that fall within
``--window`` seconds of each other and proposes a single semantic squash
message per group.  Running without ``--apply`` outputs an audit report
only; no git history is modified.

Usage::

    python scripts/squash_checkpoint_window.py
    python scripts/squash_checkpoint_window.py --window 1800 --limit 60
    python scripts/squash_checkpoint_window.py --output docs/squash-checkpoint-plan.md
"""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

CHECKPOINT_PATTERNS = (
    "auto-commit:",
    "checkpoint snapshot",
    "copilot-auto:",
)
DEFAULT_WINDOW_SECS = 300  # 5 minutes
DEFAULT_LIMIT = 40
DEFAULT_OUTPUT = Path("docs") / "squash-checkpoint-plan.md"

GitRunner = Callable[[list[str]], str]


def run_git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout


def is_checkpoint(subject: str) -> bool:
    """Return True if the commit subject matches any known checkpoint pattern."""
    s = subject.lower()
    return any(p in s for p in CHECKPOINT_PATTERNS)


@dataclass
class CommitInfo:
    hash: str
    timestamp: int
    subject: str
    files: list[str] = field(default_factory=list)


@dataclass
class SquashGroup:
    commits: list[CommitInfo]
    proposed_msg: str
    window_start: datetime
    window_end: datetime


def list_commits_with_timestamps(
    limit: int, git_runner: GitRunner = run_git
) -> list[CommitInfo]:
    """Read recent commits with Unix timestamps."""
    output = git_runner(["log", "--format=%H %ct %s", f"-{limit}"])
    commits: list[CommitInfo] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(" ", 2)
        if len(parts) < 3:
            continue
        commit_hash, ts_str, subject = parts
        try:
            timestamp = int(ts_str)
        except ValueError:
            continue
        commits.append(CommitInfo(hash=commit_hash, timestamp=timestamp, subject=subject))
    return commits


def read_changed_files(commit_hash: str, git_runner: GitRunner = run_git) -> list[str]:
    """Extract changed file paths from a commit's stat output."""
    output = git_runner(["show", "--stat", "--format=", commit_hash])
    files: list[str] = []
    for line in output.splitlines():
        if "|" not in line:
            continue
        candidate = line.split("|", 1)[0].strip()
        if candidate and "changed" not in candidate:
            files.append(candidate)
    return files


def _classify_scope(files: list[str]) -> str:
    """Return a single Conventional-Commit scope token for the changed files."""
    if not files:
        return "repo"
    scopes: list[str] = []
    for path in files:
        n = path.replace("\\", "/")
        if n.startswith("src/cli/"):
            scopes.append("cli")
        elif n.startswith("src/sources/"):
            scopes.append("sources")
        elif n.startswith("src/agents/"):
            scopes.append("agents")
        elif n.startswith("src/api/"):
            scopes.append("api")
        elif n.startswith("src/"):
            scopes.append("src")
        elif n.startswith("tests/"):
            scopes.append("tests")
        elif n.startswith("scripts/"):
            scopes.append("scripts")
        elif n.startswith("docs/") or n in {"program.md", "results.log", "engineer-log.md"}:
            scopes.append("docs")
        elif n.startswith("openspec/"):
            scopes.append("spec")
        else:
            scopes.append("repo")
    unique = list(dict.fromkeys(scopes))
    return unique[0] if len(unique) == 1 else "repo"


def _propose_squash_msg(group_commits: list[CommitInfo]) -> str:
    """Build a semantic commit message for a squash group."""
    all_files: list[str] = []
    for c in group_commits:
        all_files.extend(c.files)
    unique_files = list(dict.fromkeys(all_files))
    scope = _classify_scope(unique_files)
    top = ", ".join(unique_files[:2]) if unique_files else "working tree"
    count = len(group_commits)
    return f"chore({scope}): squash {count} checkpoint snapshots covering {top}"


def _make_group(commits: list[CommitInfo]) -> SquashGroup:
    return SquashGroup(
        commits=commits,
        proposed_msg=_propose_squash_msg(commits),
        window_start=datetime.fromtimestamp(commits[0].timestamp, tz=timezone.utc),
        window_end=datetime.fromtimestamp(commits[-1].timestamp, tz=timezone.utc),
    )


def group_checkpoint_commits(
    commits: list[CommitInfo],
    window_secs: int = DEFAULT_WINDOW_SECS,
    git_runner: GitRunner = run_git,
) -> list[SquashGroup]:
    """Group checkpoint commits that fall within window_secs of each other."""
    checkpoint_commits = [c for c in commits if is_checkpoint(c.subject)]
    if not checkpoint_commits:
        return []

    for c in checkpoint_commits:
        c.files = read_changed_files(c.hash, git_runner=git_runner)

    sorted_commits = sorted(checkpoint_commits, key=lambda c: c.timestamp)

    groups: list[SquashGroup] = []
    current: list[CommitInfo] = [sorted_commits[0]]
    for c in sorted_commits[1:]:
        if c.timestamp - current[0].timestamp <= window_secs:
            current.append(c)
        else:
            if len(current) > 1:
                groups.append(_make_group(current))
            current = [c]
    if len(current) > 1:
        groups.append(_make_group(current))
    return groups


def render_plan(
    groups: list[SquashGroup],
    checkpoint_count: int,
    total_commits: int,
    window_secs: int,
) -> str:
    """Render a markdown squash plan (audit only, no git changes)."""
    reducible = sum(len(g.commits) - 1 for g in groups)
    lines = [
        "# Checkpoint Squash Plan",
        "",
        f"- scanned_commits: {total_commits}",
        f"- checkpoint_commits: {checkpoint_count}",
        f"- squashable_groups: {len(groups)}",
        f"- commits_reducible: {reducible}",
        f"- window_secs: {window_secs}",
        "",
    ]
    if not groups:
        lines.append("No squashable checkpoint groups found.")
        lines.append("")
        lines.append("Generated by `scripts/squash_checkpoint_window.py`.")
        return "\n".join(lines)

    lines.append("## Proposed Squash Groups")
    for i, group in enumerate(groups, 1):
        lines += [
            "",
            f"### Group {i} — {len(group.commits)} commits → 1",
            f"- window_start: {group.window_start.isoformat()}",
            f"- window_end: {group.window_end.isoformat()}",
            f"- proposed_msg: `{group.proposed_msg}`",
            "- commits:",
        ]
        for c in group.commits:
            lines.append(f"  - `{c.hash[:12]}` `{c.subject}`")
        oldest = group.commits[0].hash
        lines.append(
            f"- rebase_cmd: `git rebase -i {oldest}^`"
            " (squash all, set message to proposed_msg)"
        )

    lines += [
        "",
        "---",
        "Generated by `scripts/squash_checkpoint_window.py`. No git history was modified.",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit and plan squash of checkpoint commit noise."
    )
    parser.add_argument(
        "--limit", type=int, default=DEFAULT_LIMIT,
        help="Number of recent commits to scan (default: %(default)s).",
    )
    parser.add_argument(
        "--window", type=int, default=DEFAULT_WINDOW_SECS,
        help="Group window in seconds (default: %(default)s = 5 min).",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help="Write plan to this file (default: %(default)s).",
    )
    args = parser.parse_args()

    commits = list_commits_with_timestamps(args.limit)
    checkpoints = [c for c in commits if is_checkpoint(c.subject)]
    groups = group_checkpoint_commits(commits, window_secs=args.window)
    report = render_plan(groups, len(checkpoints), len(commits), args.window)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
