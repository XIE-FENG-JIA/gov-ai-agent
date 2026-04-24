#!/usr/bin/env python3
"""Validate auto-engineer commit messages match the required semantic format.

Expected format:
    chore(auto-engineer): <type>-<summary> @<timestamp>

Where:
    <type>     = one of: feat, fix, refactor, docs, chore, test, perf, style,
                         build, ci, revert, add, update, remove, impl, patch
    <summary>  = kebab-case description (at least 2 words / parts, non-empty)
    <timestamp>= ISO 8601 date/time or epoch (YYYY-MM-DD or YYYYMMDDTHHMMSS…)

Usage::

    python scripts/validate_auto_commit_msg.py "chore(auto-engineer): feat-add-kb-index @2026-04-25"
    python scripts/validate_auto_commit_msg.py --file .git/COMMIT_EDITMSG
    echo "chore(auto-engineer): fix-llm-timeout @20260425T120000" | \\
        python scripts/validate_auto_commit_msg.py -

Exit 0 = valid, 1 = invalid (with reason printed to stderr).

Run this inside the auto-engineer runtime BEFORE handing the message to git.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# ------------------------------------------------------------------ constants

_AUTO_ENGINEER_PREFIX = "chore(auto-engineer): "

_ALLOWED_CHANGE_TYPES = (
    "feat", "fix", "refactor", "docs", "chore", "test",
    "perf", "style", "build", "ci", "revert",
    "add", "update", "remove", "impl", "patch",
)

# chore(auto-engineer): <type>-<summary> @<timestamp>
# timestamp allows: YYYY-MM-DD, YYYYMMDD, YYYYMMDDTHHMMSS, ISO with Z/offset
_AUTO_COMMIT_RE = re.compile(
    r"^chore\(auto-engineer\):\s+"
    r"(?P<type>" + "|".join(_ALLOWED_CHANGE_TYPES) + r")"
    r"-(?P<summary>[a-z0-9][a-z0-9\-]*[a-z0-9])"
    r"\s+@(?P<timestamp>\d{4}-?\d{2}-?\d{2}(?:[T\s]\d{2}:?\d{2}(?::?\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)?)$"
)

_MIN_SUMMARY_LEN = 3  # at least 3 chars after the type-


def validate(message: str) -> tuple[bool, str]:
    """Return (ok, reason). reason is empty when ok=True."""
    msg = message.strip().splitlines()[0].strip()  # inspect only subject line

    if not msg.startswith(_AUTO_ENGINEER_PREFIX):
        return False, (
            f"Message must start with '{_AUTO_ENGINEER_PREFIX}'; got: {msg!r}"
        )

    m = _AUTO_COMMIT_RE.match(msg)
    if not m:
        return False, (
            f"Message does not match 'chore(auto-engineer): <type>-<summary> @<timestamp>'; "
            f"got: {msg!r}\n"
            f"Allowed types: {', '.join(_ALLOWED_CHANGE_TYPES)}"
        )

    summary = m.group("summary")
    if len(summary) < _MIN_SUMMARY_LEN:
        return False, (
            f"Summary '{summary}' is too short (min {_MIN_SUMMARY_LEN} chars)."
        )

    return True, ""


# ------------------------------------------------------------------ I/O helpers

def _read_message(arg: str) -> str:
    if arg == "-":
        return sys.stdin.read()
    return Path(arg).read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(
            "Usage: validate_auto_commit_msg.py <message> | --file <path> | -",
            file=sys.stderr,
        )
        return 1

    if args[0] == "--file":
        if len(args) < 2:
            print("--file requires a path argument", file=sys.stderr)
            return 1
        message = _read_message(args[1])
    elif args[0] == "-":
        message = _read_message("-")
    else:
        # treat the whole arg list as the message (allows quoting)
        message = " ".join(args)

    ok, reason = validate(message)
    if ok:
        return 0
    print(f"[validate_auto_commit_msg] REJECT: {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
