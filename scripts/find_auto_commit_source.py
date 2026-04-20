from __future__ import annotations

import argparse
import csv
import io
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence


DEFAULT_OUTPUT = Path("docs") / "admin-rescue-template.md"
DEFAULT_SCAN_TARGETS = (
    Path.home() / ".claude" / "hooks",
    Path.home() / ".claude" / "settings.json",
    Path.home() / ".claude" / "settings.local.json",
    Path.home() / ".claude" / "scheduled_tasks.lock",
    Path.home() / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1",
)
PATTERNS = (
    "auto-commit:",
    "auto-engineer checkpoint",
    "AUTO-RESCUE",
    "checkpoint",
    "git commit",
)
TEXT_EXTENSIONS = {
    ".bat",
    ".cmd",
    ".json",
    ".jsonl",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".txt",
    ".vbs",
    ".yaml",
    ".yml",
}


@dataclass(frozen=True)
class CandidateHit:
    path: str
    line_no: int
    pattern: str
    snippet: str
    confidence: str
    rationale: str


@dataclass(frozen=True)
class SchedulerProbe:
    command: str
    status: str
    detail: str
    matches: tuple[str, ...] = ()


Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def run_command(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(args),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            args=list(args),
            returncode=124,
            stdout=exc.stdout or "",
            stderr=((exc.stderr or "") + "\nTIMEOUT: command exceeded 8s").strip(),
        )


def _iter_files(target: Path) -> Iterable[Path]:
    if target.is_file():
        yield target
        return
    if not target.exists():
        return
    for path in target.rglob("*"):
        if path.is_file():
            yield path


def _should_scan(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    return path.name in {"scheduled_tasks.lock", "settings.json", "settings.local.json"}


def _classify_hit(path: Path, pattern: str) -> tuple[str, str]:
    normalized = str(path).replace("\\", "/").lower()
    if pattern in {"auto-commit:", "auto-engineer checkpoint", "AUTO-RESCUE"}:
        return "high", "exact rescue template token present"
    if normalized.endswith("scheduled_tasks.lock") or pattern == "scheduler-lock":
        return "med", "scheduler coordination artifact present"
    if "settings" in normalized or "/hooks/" in normalized:
        return "med", "runtime hook configuration references related behavior"
    return "low", "supporting clue only"


def scan_paths(targets: Sequence[Path], patterns: Sequence[str] = PATTERNS) -> list[CandidateHit]:
    hits: list[CandidateHit] = []
    seen: set[tuple[str, int, str]] = set()
    lowered_patterns = [(pattern, pattern.lower()) for pattern in patterns]

    for target in targets:
        if target.is_file() and target.name == "scheduled_tasks.lock":
            confidence, rationale = _classify_hit(target, "scheduler-lock")
            hits.append(
                CandidateHit(
                    path=str(target),
                    line_no=1,
                    pattern="scheduler-lock",
                    snippet="scheduler coordination lock present",
                    confidence=confidence,
                    rationale=rationale,
                )
            )
        for path in _iter_files(target):
            if not _should_scan(path):
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line_no, line in enumerate(content.splitlines(), start=1):
                lowered = line.lower()
                for pattern, lowered_pattern in lowered_patterns:
                    if lowered_pattern not in lowered:
                        continue
                    confidence, rationale = _classify_hit(path, pattern)
                    key = (str(path), line_no, pattern)
                    if key in seen:
                        continue
                    seen.add(key)
                    hits.append(
                        CandidateHit(
                            path=str(path),
                            line_no=line_no,
                            pattern=pattern,
                            snippet=line.strip(),
                            confidence=confidence,
                            rationale=rationale,
                        )
                    )
    hits.sort(key=lambda item: ({"high": 0, "med": 1, "low": 2}[item.confidence], item.path, item.line_no))
    return hits


def probe_scheduler(runner: Runner = run_command) -> SchedulerProbe:
    command = r"C:\Windows\System32\schtasks.exe /query /fo CSV /v"
    completed = runner([r"C:\Windows\System32\schtasks.exe", "/query", "/fo", "CSV", "/v"])
    combined = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
    detail = combined.strip() or f"exit={completed.returncode}"
    if completed.returncode != 0:
        return SchedulerProbe(command=command, status="unavailable", detail=detail)

    reader = csv.DictReader(io.StringIO(completed.stdout))
    matches: list[str] = []
    for row in reader:
        task_name = row.get("TaskName", "")
        task_to_run = row.get("Task To Run", "")
        joined = f"{task_name} {task_to_run}".lower()
        if any(token in joined for token in ("claude", "codex", "auto", "rescue", "engineer")):
            matches.append(f"{task_name} => {task_to_run}")
    if matches:
        return SchedulerProbe(command=command, status="candidate-found", detail="scheduler candidates found", matches=tuple(matches[:10]))
    return SchedulerProbe(command=command, status="no-match", detail="scheduler query returned no related task names")


def summarize_findings(hits: Sequence[CandidateHit], scheduler: SchedulerProbe) -> list[str]:
    summary: list[str] = []
    exact_hits = [item for item in hits if item.confidence == "high"]
    if exact_hits:
        summary.append(f"Scanned local admin surfaces and found {len(exact_hits)} exact rescue-token hits.")
    else:
        summary.append("Scanned local admin surfaces and found no exact `auto-commit:` template file.")
    if scheduler.status == "candidate-found":
        summary.append("Task Scheduler returned related tasks; inspect them before touching repo-side configs.")
    elif scheduler.status == "unavailable":
        summary.append("Task Scheduler query failed in this shell; external scheduler/wrapper remains the leading suspect.")
    else:
        summary.append("Task Scheduler query returned no obvious Claude/Codex rescue task names.")
    return summary


def render_report(hits: Sequence[CandidateHit], scheduler: SchedulerProbe, targets: Sequence[Path]) -> str:
    lines = [
        "# Admin Rescue Template",
        "",
        "## §candidates",
        "",
        f"- scanned_targets: {len(targets)}",
        f"- hit_count: {len(hits)}",
        f"- scheduler_status: {scheduler.status}",
    ]
    for line in summarize_findings(hits, scheduler):
        lines.append(f"- summary: {line}")
    lines.extend(
        [
            "",
            "| confidence | path | line | pattern | why it matters | snippet |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    if hits:
        for hit in hits:
            lines.append(
                "| "
                f"{hit.confidence} | `{escape_cell(hit.path)}` | {hit.line_no} | "
                f"`{escape_cell(hit.pattern)}` | {escape_cell(hit.rationale)} | "
                f"{escape_cell(hit.snippet)} |"
            )
    else:
        lines.append("| low | `(none)` | - | - | no exact local template file found | - |")

    lines.extend(
        [
            "",
            "## §template-diff",
            "",
            "Replace the Admin rescue commit message template. Keep the `AUTO-RESCUE` audit token in the body, not the subject.",
            "",
            "```diff",
            "- auto-commit: auto-engineer checkpoint (<ts>)",
            "+ chore(rescue): restore auto-engineer working tree (<ISO8601>)",
            "+",
            "+ AUTO-RESCUE: files=<N>; source=session-wrapper",
            "```",
            "",
            "Recommended subject fallback when file count is known:",
            "",
            "```text",
            "chore(rescue): restore auto-engineer working tree (2026-04-20T17:20:00+08:00)",
            "```",
            "",
            "Recommended body:",
            "",
            "```text",
            "AUTO-RESCUE: files=3; source=session-wrapper",
            "",
            "- results.log",
            "- program.md",
            "- docs/admin-rescue-template.md",
            "```",
            "",
            "## §admin-action",
            "",
            "1. Inspect the external wrapper or scheduler that stages rescue commits. Repo hooks and PowerShell profile do not define the `auto-commit:` template.",
            "2. Change only the commit message formatter. Do not change the rescue staging logic yet.",
            "3. Re-run one rescue cycle and verify `git log --oneline -5` has no `auto-commit:` or `checkpoint` subject.",
            "4. Keep `AUTO-RESCUE` in the commit body so `results.log` and git history still correlate.",
            "5. If Task Scheduler remains inaccessible in-shell, inspect the Admin session launcher manually from elevated PowerShell.",
            "",
            "## scheduler-probe",
            "",
            f"- command: `{scheduler.command}`",
            f"- status: `{scheduler.status}`",
            f"- detail: {escape_cell(scheduler.detail)}",
        ]
    )
    if scheduler.matches:
        lines.append("- matches:")
        for match in scheduler.matches:
            lines.append(f"  - {match}")
    else:
        lines.append("- matches: none")
    lines.append("")
    lines.append("Generated by `scripts/find_auto_commit_source.py`.")
    return "\n".join(lines)


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Locate likely AUTO-RESCUE commit-message sources.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Markdown report output path.")
    parser.add_argument(
        "--scan-target",
        action="append",
        default=None,
        help="Extra file or directory to scan. May be passed multiple times.",
    )
    return parser


def resolve_targets(extra_targets: Sequence[str] | None = None) -> list[Path]:
    targets = list(DEFAULT_SCAN_TARGETS)
    if extra_targets:
        targets.extend(Path(item).expanduser() for item in extra_targets)
    unique: list[Path] = []
    seen: set[str] = set()
    for path in targets:
        key = os.path.normcase(str(path))
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    targets = resolve_targets(args.scan_target)
    hits = scan_paths(targets)
    scheduler = probe_scheduler()
    write_report(args.output, render_report(hits, scheduler, targets))
    print(f"wrote {args.output} with {len(hits)} candidate hits; scheduler={scheduler.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
