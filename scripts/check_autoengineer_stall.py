#!/usr/bin/env python3
"""Auto-engineer stall gate.

Reads ``.auto-engineer.state.json`` and reports whether the auto-engineer
loop is still making forward progress. Intended as a startup / cron gate
so the pua-loop or watchdog can notify when codex daemon dies silently.

Status model::

    OK       last_update within threshold (default 2h)
    STALLED  last_update older than threshold
    MISSING  state file does not exist
    CORRUPT  state file exists but cannot be parsed / missing keys
    FUTURE   last_update is in the future (clock skew / test bug)

Exit codes::

    0 = OK
    1 = STALLED / FUTURE (treat as alert)
    2 = MISSING / CORRUPT (treat as configuration problem)

Usage::

    python scripts/check_autoengineer_stall.py
    python scripts/check_autoengineer_stall.py --json
    python scripts/check_autoengineer_stall.py --threshold-hours 4 --human
    python scripts/check_autoengineer_stall.py --state path/to/state.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DEFAULT_STATE = Path(".auto-engineer.state.json")
_DEFAULT_THRESHOLD_HOURS = 2.0


@dataclass
class StallReport:
    status: str
    threshold_hours: float
    age_seconds: float | None
    last_update: str | None
    round_: str | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["round"] = d.pop("round_")
        return d


def _parse_iso(ts: str) -> datetime:
    # Python 3.11 fromisoformat accepts "+08:00"; older pythons don't
    return datetime.fromisoformat(ts)


def check(
    state_path: Path,
    threshold_hours: float = _DEFAULT_THRESHOLD_HOURS,
    now: datetime | None = None,
) -> StallReport:
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if not state_path.exists():
        return StallReport(
            status="MISSING",
            threshold_hours=threshold_hours,
            age_seconds=None,
            last_update=None,
            round_=None,
            reason=f"state file not found: {state_path}",
        )

    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return StallReport(
            status="CORRUPT",
            threshold_hours=threshold_hours,
            age_seconds=None,
            last_update=None,
            round_=None,
            reason=f"cannot parse state file: {exc}",
        )

    last_update = raw.get("last_update")
    round_ = raw.get("round")
    if not last_update:
        return StallReport(
            status="CORRUPT",
            threshold_hours=threshold_hours,
            age_seconds=None,
            last_update=None,
            round_=round_,
            reason="state file missing 'last_update' key",
        )

    try:
        ts = _parse_iso(last_update)
    except ValueError as exc:
        return StallReport(
            status="CORRUPT",
            threshold_hours=threshold_hours,
            age_seconds=None,
            last_update=last_update,
            round_=round_,
            reason=f"'last_update' not ISO 8601: {exc}",
        )

    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    age = (now - ts).total_seconds()
    threshold_seconds = threshold_hours * 3600.0

    if age < 0:
        return StallReport(
            status="FUTURE",
            threshold_hours=threshold_hours,
            age_seconds=age,
            last_update=last_update,
            round_=round_,
            reason=f"last_update is in the future by {-age:.0f}s (clock skew?)",
        )
    if age > threshold_seconds:
        hours = age / 3600.0
        return StallReport(
            status="STALLED",
            threshold_hours=threshold_hours,
            age_seconds=age,
            last_update=last_update,
            round_=round_,
            reason=(
                f"auto-engineer last_update is {hours:.1f}h old "
                f"(> {threshold_hours}h threshold) — codex daemon likely dead"
            ),
        )
    return StallReport(
        status="OK",
        threshold_hours=threshold_hours,
        age_seconds=age,
        last_update=last_update,
        round_=round_,
        reason=f"last_update {age/60:.1f} min old (within {threshold_hours}h)",
    )


_EXIT_CODE = {"OK": 0, "STALLED": 1, "FUTURE": 1, "MISSING": 2, "CORRUPT": 2}


def _format_human(report: StallReport) -> str:
    lines = [f"auto-engineer stall check: {report.status}"]
    if report.round_:
        lines.append(f"  round        : {report.round_}")
    if report.last_update:
        lines.append(f"  last_update  : {report.last_update}")
    if report.age_seconds is not None:
        lines.append(
            f"  age          : {report.age_seconds:.0f}s "
            f"({report.age_seconds/3600.0:.2f}h)"
        )
    lines.append(f"  threshold    : {report.threshold_hours}h")
    lines.append(f"  reason       : {report.reason}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--state", type=Path, default=_DEFAULT_STATE)
    parser.add_argument(
        "--threshold-hours",
        type=float,
        default=_DEFAULT_THRESHOLD_HOURS,
        help="stall threshold in hours (default 2.0)",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    parser.add_argument("--human", action="store_true", help="emit readable report")
    args = parser.parse_args(argv)

    report = check(args.state, args.threshold_hours)

    # JSON always goes to stdout (machine-readable single source of truth).
    # --human just *additionally* emits a readable summary to stderr.
    print(json.dumps(report.to_dict(), ensure_ascii=False))
    if args.human:
        print(_format_human(report), file=sys.stderr)

    return _EXIT_CODE[report.status]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
