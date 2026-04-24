#!/usr/bin/env python3
"""Check .git ACL state and report task-pool eligibility.

Run at session/auto-engineer startup. If foreign SID DENY ACEs are found
on .git/, switch downstream task pools to **read-only mode** — block any
commit/push/rebase/git-hook-install task, allow only inspection / pytest /
docs work.

Exit codes:
    0 — clean (no foreign DENY); full task pool available
    1 — DENY present; downstream consumers should run read-only

Output (to stdout, machine-parseable JSON):
    {"status": "clean" | "denied",
     "deny_count": int,
     "foreign_sids": [str, ...],
     "recommended_mode": "full" | "read-only"}

Use:
    python scripts/check_acl_state.py
    python scripts/check_acl_state.py --human   # pretty-printed for humans
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# Local AD/computer SIDs that legitimately appear in .git (Administrator + System)
_TRUSTED_SID_PREFIXES = (
    "S-1-5-32-",          # BUILTIN\Administrators
    "S-1-5-18",           # NT AUTHORITY\SYSTEM
    "S-1-5-11",           # NT AUTHORITY\Authenticated Users
    "S-1-5-21-2402424919-1912629089-3910208045-",  # Local machine SID prefix (this host)
)


def _run_icacls(target: Path) -> str:
    """Invoke icacls on target. Returns raw text output."""
    cmd = ["icacls", str(target)]
    result = subprocess.run(  # noqa: S603,S607 — icacls is fixed Windows tool
        cmd, capture_output=True, text=True, timeout=10,
    )
    return result.stdout


def parse_deny_aces(icacls_output: str) -> list[tuple[str, str]]:
    """Parse icacls output, return [(sid, permissions), ...] for DENY ACEs.

    Format example::

        S-1-5-21-541253457-2268935619-321007557-692795393:(DENY)(W,D,Rc,DC)
        S-1-5-21-541253457-2268935619-321007557-692795393:(OI)(CI)(IO)(DENY)(W,D,Rc,GW,DC)
    """
    # icacls 第一行帶檔名（".git S-1-..."），後續行只有縮排；用無錨 search 涵蓋兩種
    deny_re = re.compile(r"(S-1-[\d-]+):.*?\(DENY\)\((?P<perms>[^)]+)\)")
    out = []
    for line in icacls_output.splitlines():
        m = deny_re.search(line)
        if m:
            out.append((m.group(1), m.group("perms")))
    return out


def is_foreign_sid(sid: str) -> bool:
    """True if the SID is NOT in the trusted local list."""
    return not any(sid.startswith(p) for p in _TRUSTED_SID_PREFIXES)


def check(target: Path | None = None) -> dict:
    target = target or Path(".git")
    if not target.exists():
        return {
            "status": "clean",
            "deny_count": 0,
            "foreign_sids": [],
            "recommended_mode": "full",
            "note": f"target {target} not found — assumed clean",
        }
    output = _run_icacls(target)
    deny_aces = parse_deny_aces(output)
    foreign = sorted({sid for sid, _ in deny_aces if is_foreign_sid(sid)})

    if foreign:
        return {
            "status": "denied",
            "deny_count": len(deny_aces),
            "foreign_sids": foreign,
            "recommended_mode": "read-only",
        }
    return {
        "status": "clean",
        "deny_count": len(deny_aces),
        "foreign_sids": [],
        "recommended_mode": "full",
    }


def _human_print(report: dict) -> None:
    print(f"ACL status: {report['status']}")
    print(f"DENY ACE count: {report['deny_count']}")
    print(f"Foreign SIDs: {report['foreign_sids'] or '(none)'}")
    print(f"Recommended mode: {report['recommended_mode']}")
    if report["status"] == "denied":
        print("\n[guard] downstream task pools should switch to read-only:")
        print("  - block: git commit / push / rebase / hooks/* install")
        print("  - allow: pytest / docs / read-only inspection")
        print("\nResolution: P0.D — Admin must remove foreign SID DENY ACEs from .git")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default=".git", help="path to check (default: .git)")
    parser.add_argument("--human", action="store_true", help="pretty-print instead of JSON")
    args = parser.parse_args(argv[1:])

    report = check(Path(args.target))
    if args.human:
        _human_print(report)
    else:
        print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "clean" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
