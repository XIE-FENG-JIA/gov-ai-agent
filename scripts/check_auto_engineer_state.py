#!/usr/bin/env python3
"""Check auto-engineer state file for stale-running orphan daemons.

Reads ``.auto-engineer.state.json``. If ``status == "running"`` but
``last_update`` is older than the threshold (default 2 hours), the daemon
is almost certainly dead and the state file is lying. Emit a structured
report so supervise/watchdog can react instead of trusting the JSON blindly.

Born from the 2026-04-22→24 incident where the codex daemon died for 40 hr
while ``state.json`` still claimed ``running`` — pua-loop only noticed
because a human asked.

Exit codes:
    0 — fresh OR file absent (no auto-engineer expected)
    1 — stale-running orphan detected (or PID is gone)
    2 — state file malformed

Output (JSON to stdout)::

    {"status": "running" | "idle" | "stale" | "orphan" | "absent" | "malformed",
     "round": int | null,
     "last_update": str | null,
     "age_seconds": int | null,
     "pid": int | null,
     "pid_alive": bool | null,
     "threshold_seconds": int,
     "recommendation": str}
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_THRESHOLD_SECONDS = 2 * 60 * 60  # 2 hours


def _parse_timestamp(ts: str) -> datetime | None:
    """Parse ISO-8601 timestamp; return None on failure.

    Tolerates trailing ``+08:00`` or ``Z``.
    """
    if not ts:
        return None
    try:
        # Handle "Z" suffix
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None


def _pid_alive(pid: int) -> bool:
    """Best-effort 'is this PID still alive?' check.

    Avoids importing psutil (heavy dep). On Windows uses tasklist via os; on
    POSIX uses os.kill(pid, 0).
    """
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            import subprocess
            result = subprocess.run(  # noqa: S603,S607
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            return str(pid) in result.stdout
        os.kill(pid, 0)
        return True
    except (OSError, subprocess.SubprocessError, ImportError):
        return False


def check(state_path: Path | None = None, *, threshold_seconds: int = DEFAULT_THRESHOLD_SECONDS,
          now: datetime | None = None) -> dict:
    state_path = state_path or Path(".auto-engineer.state.json")
    now = now or datetime.now(timezone.utc)

    if not state_path.exists():
        return {
            "status": "absent",
            "round": None, "last_update": None, "age_seconds": None,
            "pid": None, "pid_alive": None,
            "threshold_seconds": threshold_seconds,
            "recommendation": "no auto-engineer expected; pua-loop session-driven OK",
        }

    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {
            "status": "malformed",
            "round": None, "last_update": None, "age_seconds": None,
            "pid": None, "pid_alive": None,
            "threshold_seconds": threshold_seconds,
            "recommendation": f"state file unreadable ({exc}); inspect manually",
        }

    declared_status = raw.get("status", "unknown")
    last_update_ts = _parse_timestamp(raw.get("last_update", ""))
    pid_raw = raw.get("pid")
    try:
        pid = int(pid_raw) if pid_raw is not None else None
    except (TypeError, ValueError):
        pid = None
    round_raw = raw.get("round")
    try:
        round_n = int(round_raw) if round_raw is not None else None
    except (TypeError, ValueError):
        round_n = None

    age_seconds: int | None
    if last_update_ts is not None:
        if last_update_ts.tzinfo is None:
            last_update_ts = last_update_ts.replace(tzinfo=timezone.utc)
        age_seconds = int((now - last_update_ts).total_seconds())
    else:
        age_seconds = None

    pid_alive = _pid_alive(pid) if pid is not None else None

    if declared_status != "running":
        # idle / done / stopped — treat as fresh truth from the daemon
        return {
            "status": declared_status,
            "round": round_n,
            "last_update": raw.get("last_update"),
            "age_seconds": age_seconds,
            "pid": pid, "pid_alive": pid_alive,
            "threshold_seconds": threshold_seconds,
            "recommendation": "honor declared non-running status",
        }

    # status == "running"; check if it's actually alive
    if pid is not None and not pid_alive:
        return {
            "status": "orphan",
            "round": round_n,
            "last_update": raw.get("last_update"),
            "age_seconds": age_seconds,
            "pid": pid, "pid_alive": False,
            "threshold_seconds": threshold_seconds,
            "recommendation": (
                f"PID {pid} dead but state.json says 'running'; "
                "lock orphan, mark state stale, allow pua-loop to take over"
            ),
        }

    if age_seconds is not None and age_seconds > threshold_seconds:
        return {
            "status": "stale",
            "round": round_n,
            "last_update": raw.get("last_update"),
            "age_seconds": age_seconds,
            "pid": pid, "pid_alive": pid_alive,
            "threshold_seconds": threshold_seconds,
            "recommendation": (
                f"last update {age_seconds}s ago > {threshold_seconds}s threshold; "
                "daemon hung or zombie — investigate before claiming progress"
            ),
        }

    return {
        "status": "running",
        "round": round_n,
        "last_update": raw.get("last_update"),
        "age_seconds": age_seconds,
        "pid": pid, "pid_alive": pid_alive,
        "threshold_seconds": threshold_seconds,
        "recommendation": "fresh; trust state",
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default=".auto-engineer.state.json")
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD_SECONDS,
                        help="seconds past last_update before flagging stale (default 7200)")
    parser.add_argument("--human", action="store_true")
    args = parser.parse_args(argv[1:])

    report = check(Path(args.state), threshold_seconds=args.threshold)
    if args.human:
        print(f"auto-engineer status: {report['status']}")
        print(f"  round         {report['round']}")
        print(f"  last_update   {report['last_update']}")
        print(f"  age_seconds   {report['age_seconds']}")
        print(f"  pid           {report['pid']} (alive={report['pid_alive']})")
        print(f"  threshold     {report['threshold_seconds']}s")
        print(f"  → {report['recommendation']}")
    else:
        print(json.dumps(report, ensure_ascii=False))

    if report["status"] in ("stale", "orphan", "malformed"):
        return 1 if report["status"] != "malformed" else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
