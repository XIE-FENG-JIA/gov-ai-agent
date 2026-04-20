from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Callable, Iterable


AUTO_COMMIT_PREFIX = "auto-commit:"
DEFAULT_LIMIT = 40
DEFAULT_OUTPUT = Path("docs") / "rescue-commit-plan.md"
DEFAULT_RANGE = "HEAD~20..HEAD"
AUTO_RESCUE_TOKEN = "AUTO-RESCUE"


@dataclass(frozen=True)
class CommitSuggestion:
    commit_hash: str
    current_msg: str
    proposed_msg: str
    files_top3: str
    confidence: str


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


def run_command(args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def list_recent_commits(limit: int, git_runner: GitRunner = run_git) -> list[tuple[str, str]]:
    output = git_runner(["log", f"--format=%H %s", f"-{limit}"])
    commits: list[tuple[str, str]] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        commit_hash, _, subject = line.partition(" ")
        if not commit_hash or not subject:
            continue
        commits.append((commit_hash, subject))
    return commits


def read_commit_stat_lines(commit_hash: str, git_runner: GitRunner = run_git) -> list[str]:
    output = git_runner(["show", "--stat", "--format=", commit_hash])
    return [line.rstrip() for line in output.splitlines() if line.strip()]


def extract_changed_files(stat_lines: Iterable[str]) -> list[str]:
    files: list[str] = []
    for line in stat_lines:
        if "|" not in line:
            continue
        candidate = line.split("|", 1)[0].strip()
        if candidate and "changed" not in candidate:
            files.append(candidate)
    return files


def classify_scope(files: list[str]) -> tuple[str, str]:
    if not files:
        return "repo", "low"

    scopes: list[str] = []
    for path in files:
        normalized = path.replace("\\", "/")
        if normalized.startswith("src/cli/"):
            scopes.append("cli")
        elif normalized.startswith("src/sources/"):
            scopes.append("sources")
        elif normalized.startswith("src/agents/"):
            scopes.append("agents")
        elif normalized.startswith("src/integrations/"):
            scopes.append("integrations")
        elif normalized.startswith("src/api/"):
            scopes.append("api")
        elif normalized.startswith("tests/"):
            scopes.append("tests")
        elif normalized.startswith("scripts/"):
            scopes.append("scripts")
        elif normalized.startswith("docs/") or normalized in {
            "program.md",
            "results.log",
            "engineer-log.md",
        }:
            scopes.append("docs")
        elif normalized.startswith("openspec/"):
            scopes.append("spec")
        else:
            scopes.append("repo")

    unique_scopes = list(dict.fromkeys(scopes))
    if len(unique_scopes) == 1:
        return unique_scopes[0], "high"
    if len(unique_scopes) == 2:
        return unique_scopes[0], "med"
    return "repo", "low"


def classify_change_type(files: list[str], scope: str) -> str:
    normalized = [path.replace("\\", "/") for path in files]
    if normalized and all(path.startswith("tests/") for path in normalized):
        return "test"
    if normalized and all(
        path.startswith("docs/")
        or path in {"program.md", "results.log", "engineer-log.md"}
        or path.startswith("openspec/")
        for path in normalized
    ):
        return "docs"
    if scope == "scripts":
        return "feat"
    if scope == "repo":
        return "chore"
    return "feat"


def build_summary(files: list[str], scope: str, change_type: str) -> str:
    top = ", ".join(files[:2]) if files else "working tree"
    if change_type == "docs":
        return f"sync {scope} progress for {top}"
    if change_type == "test":
        return f"cover {scope} changes in {top}"
    if change_type == "chore":
        return f"capture auto-rescue changes in {top}"
    if change_type == "feat" and scope == "scripts":
        return f"add audit tooling for {top}"
    return f"sync {scope} changes in {top}"


def propose_message(files: list[str]) -> tuple[str, str]:
    scope, confidence = classify_scope(files)
    change_type = classify_change_type(files, scope)
    summary = build_summary(files, scope, change_type)
    return f"{change_type}({scope}): {summary}", confidence


def collect_suggestions(limit: int = DEFAULT_LIMIT, git_runner: GitRunner = run_git) -> list[CommitSuggestion]:
    suggestions: list[CommitSuggestion] = []
    for commit_hash, subject in list_recent_commits(limit, git_runner=git_runner):
        if not subject.startswith(AUTO_COMMIT_PREFIX):
            continue
        stat_lines = read_commit_stat_lines(commit_hash, git_runner=git_runner)
        files = extract_changed_files(stat_lines)
        proposed_msg, confidence = propose_message(files)
        suggestions.append(
            CommitSuggestion(
                commit_hash=commit_hash,
                current_msg=subject,
                proposed_msg=proposed_msg,
                files_top3=", ".join(files[:3]) if files else "(no file stats)",
                confidence=confidence,
            )
        )
    return suggestions


def render_report(suggestions: list[CommitSuggestion], limit: int, mode: str = "audit-only") -> str:
    lines = [
        "# Rescue Commit Plan",
        "",
        f"- mode: {mode}",
        f"- scanned_commits: {limit}",
        f"- rewrite_candidates: {len(suggestions)}",
        f"- destructive_ops: {'none' if mode == 'audit-only' else 'git filter-branch --msg-filter'}",
        "",
        "| commit_hash | current_msg | proposed_msg | files_top3 | confidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in suggestions:
        lines.append(
            "| "
            f"`{item.commit_hash[:12]}` | {escape_cell(item.current_msg)} | "
            f"{escape_cell(item.proposed_msg)} | {escape_cell(item.files_top3)} | "
            f"{item.confidence} |"
        )
    if not suggestions:
        lines.append("| `(none)` | no auto-commit messages found | - | - | low |")
    lines.append("")
    lines.append("Generated by `scripts/rewrite_auto_commit_msgs.py`. No git history was changed.")
    return "\n".join(lines)


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _quote_for_shell(value: str) -> str:
    return shlex.quote(value)


def _build_message_filter_script() -> str:
    return (
        "import json, os, sys\n"
        "mapping = json.loads(os.environ['GOV_AI_REWRITE_MAP'])\n"
        "commit = os.environ.get('GIT_COMMIT', '')\n"
        "original = sys.stdin.read()\n"
        "sys.stdout.write(mapping.get(commit, original))\n"
    )


def git_acl_has_deny(git_dir: Path = Path(".git")) -> bool:
    if os.name != "nt":
        return False
    completed = run_command(["icacls", str(git_dir)])
    return completed.returncode == 0 and "DENY" in completed.stdout.upper()


def apply_rewrites(
    suggestions: list[CommitSuggestion],
    commit_range: str,
    command_runner: Callable[[list[str], dict[str, str] | None], subprocess.CompletedProcess[str]] = run_command,
) -> int:
    if not suggestions:
        print("no auto-commit candidates found; nothing to rewrite")
        return 0

    rewrite_map = {
        item.commit_hash: f"{item.proposed_msg} [{AUTO_RESCUE_TOKEN}]"
        for item in suggestions
    }
    base_env = os.environ.copy()
    base_env["GOV_AI_REWRITE_MAP"] = json.dumps(rewrite_map, ensure_ascii=True)

    with tempfile.TemporaryDirectory(prefix="rewrite-auto-commit-") as tmp_dir:
        script_path = Path(tmp_dir) / "msg_filter.py"
        script_path.write_text(_build_message_filter_script(), encoding="utf-8")
        msg_filter = f"{_quote_for_shell(sys.executable)} {_quote_for_shell(str(script_path))}"
        completed = command_runner(
            [
                "git",
                "filter-branch",
                "-f",
                "--msg-filter",
                msg_filter,
                commit_range,
            ],
            base_env,
        )

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        detail = stderr or stdout or "unknown git filter-branch failure"
        print(f"rewrite failed: {detail}", file=sys.stderr)
        return completed.returncode

    print(
        f"rewrote {len(suggestions)} auto-commit messages in {commit_range} "
        f"and preserved token {AUTO_RESCUE_TOKEN}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit auto-commit messages and propose conventional rewrites.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Number of recent commits to scan.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Markdown report path.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Rewrite matching auto-commit subjects inside the selected git range.",
    )
    parser.add_argument(
        "--range",
        dest="commit_range",
        default=DEFAULT_RANGE,
        help="Git revision range to rewrite when --apply is set.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    suggestions = collect_suggestions(limit=args.limit)
    mode = "apply-ready" if args.apply else "audit-only"
    write_report(args.output, render_report(suggestions, limit=args.limit, mode=mode))
    print(f"wrote {args.output} with {len(suggestions)} rewrite candidates")

    if not args.apply:
        return 0
    if git_acl_has_deny():
        print(
            "apply blocked: .git ACL contains DENY entries; audit report was still generated",
            file=sys.stderr,
        )
        return 2
    return apply_rewrites(suggestions, args.commit_range)


if __name__ == "__main__":
    raise SystemExit(main())
