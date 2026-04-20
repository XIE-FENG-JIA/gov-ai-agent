from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_STATUS_FILTER = ("BLOCKED-ACL",)


@dataclass(frozen=True)
class LogEntry:
    raw: str
    timestamp: datetime | None
    task_id: str | None
    status: str | None
    summary: str | None
    files: str | None


@dataclass(frozen=True)
class DedupGroup:
    first_entry: LogEntry
    count: int
    first_time: str
    last_time: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deduplicate repeated results.log entries.")
    parser.add_argument("path", type=Path, help="Path to results.log")
    parser.add_argument(
        "--status",
        action="append",
        default=None,
        help="Status label to dedupe. Defaults to BLOCKED-ACL. May be passed multiple times.",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the input file instead of writing a .dedup sidecar.",
    )
    return parser


def parse_entry(line: str) -> LogEntry:
    stripped = line.rstrip("\n")
    parts = [part.strip() for part in stripped.split("|")]
    if len(parts) < 5:
        return LogEntry(raw=stripped, timestamp=None, task_id=None, status=None, summary=None, files=None)

    timestamp = _parse_timestamp(parts[0])
    task_id = _strip_brackets(parts[1])
    status = _strip_brackets(parts[2])
    summary = parts[3]
    files = parts[4]
    return LogEntry(
        raw=stripped,
        timestamp=timestamp,
        task_id=task_id,
        status=status,
        summary=summary,
        files=files,
    )


def _parse_timestamp(token: str) -> datetime | None:
    cleaned = _strip_brackets(token)
    try:
        return datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _strip_brackets(value: str) -> str:
    if value.startswith("[") and value.endswith("]"):
        return value[1:-1]
    return value


def summary_hash(summary: str | None) -> str:
    normalized = (summary or "").strip().encode("utf-8")
    return hashlib.sha1(normalized).hexdigest()


def dedupe_lines(lines: Iterable[str], statuses: Sequence[str] = DEFAULT_STATUS_FILTER) -> tuple[list[str], int]:
    parsed_entries = [parse_entry(line) for line in lines]
    active_statuses = {status.upper() for status in statuses}
    groups: dict[tuple[str, str, str, str], DedupGroup] = {}
    output: list[str] = []
    removed = 0

    for entry in parsed_entries:
        if (
            entry.timestamp is None
            or entry.task_id is None
            or entry.status is None
            or entry.summary is None
            or entry.status.upper() not in active_statuses
        ):
            output.append(entry.raw)
            continue

        key = (
            entry.timestamp.strftime("%Y-%m-%d"),
            entry.task_id,
            entry.status.upper(),
            summary_hash(entry.summary),
        )
        existing = groups.get(key)
        if existing is None:
            time_token = entry.timestamp.strftime("%H:%M:%S")
            groups[key] = DedupGroup(
                first_entry=entry,
                count=1,
                first_time=time_token,
                last_time=time_token,
            )
            output.append(entry.raw)
            continue

        removed += 1
        groups[key] = DedupGroup(
            first_entry=existing.first_entry,
            count=existing.count + 1,
            first_time=existing.first_time,
            last_time=entry.timestamp.strftime("%H:%M:%S"),
        )

    return apply_suffixes(output, groups), removed


def apply_suffixes(lines: list[str], groups: dict[tuple[str, str, str, str], DedupGroup]) -> list[str]:
    rewritten: list[str] = []
    for line in lines:
        entry = parse_entry(line)
        if (
            entry.timestamp is None
            or entry.task_id is None
            or entry.status is None
            or entry.summary is None
        ):
            rewritten.append(line)
            continue

        key = (
            entry.timestamp.strftime("%Y-%m-%d"),
            entry.task_id,
            entry.status.upper(),
            summary_hash(entry.summary),
        )
        group = groups.get(key)
        if group is None or group.count == 1:
            rewritten.append(line)
            continue

        suffix = f" count={group.count} (first={group.first_time} last={group.last_time})"
        if suffix in line:
            rewritten.append(line)
            continue
        rewritten.append(f"{line}{suffix}")
    return rewritten


def output_path_for(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.name}.dedup")


def render_output(lines: Sequence[str]) -> str:
    return "\n".join(lines) + ("\n" if lines else "")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    statuses = tuple(args.status or DEFAULT_STATUS_FILTER)

    source_text = args.path.read_text(encoding="utf-8")
    deduped_lines, removed = dedupe_lines(source_text.splitlines(), statuses=statuses)
    rendered = render_output(deduped_lines)

    if args.in_place:
        args.path.write_text(rendered, encoding="utf-8")
    else:
        output_path_for(args.path).write_text(rendered, encoding="utf-8")

    print(rendered, end="")
    print(
        f"# dedupe-summary removed={removed} output={'in-place' if args.in_place else output_path_for(args.path)}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
