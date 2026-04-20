from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


AUTO_COMMIT_PREFIX = "auto-commit:"
DEFAULT_LIMIT = 40
DEFAULT_OUTPUT = Path("docs") / "rescue-commit-plan.md"


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


def render_report(suggestions: list[CommitSuggestion], limit: int) -> str:
    lines = [
        "# Rescue Commit Plan",
        "",
        "- mode: audit-only",
        f"- scanned_commits: {limit}",
        f"- rewrite_candidates: {len(suggestions)}",
        "- destructive_ops: none",
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit auto-commit messages and propose conventional rewrites.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Number of recent commits to scan.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Markdown report path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    suggestions = collect_suggestions(limit=args.limit)
    write_report(args.output, render_report(suggestions, limit=args.limit))
    print(f"wrote {args.output} with {len(suggestions)} rewrite candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
