#!/usr/bin/env python3
"""Commit message linter.

Reject naked formats like ``auto-commit: checkpoint`` / ``WIP`` / ``fix``.
Require a Conventional-Commit-style prefix that names what changed and why.

Usage::

    python scripts/commit_msg_lint.py <path-to-commit-msg-file>
    echo "feat(api): add foo" | python scripts/commit_msg_lint.py -

Exit 0 on accept, 1 on reject (with stderr explanation).

Wire as ``.git/hooks/commit-msg`` (after ACL is unblocked) or run manually
in CI / pre-push hooks.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Conventional Commit-style allowed types
_ALLOWED_TYPES = (
    "feat", "fix", "refactor", "docs", "chore",
    "test", "perf", "style", "build", "ci", "revert",
)
_HEADER_RE = re.compile(
    rf"^(?P<type>{'|'.join(_ALLOWED_TYPES)})"
    r"(?:\([^)]+\))?"  # optional (scope)
    r"!?"  # optional breaking-change marker
    r":\s+(?P<subject>.+)$"
)

# Naked / lazy patterns — reject loudly
# Background: 2026-04-25 LOOP3 抓到 auto-engineer / copilot 兩條 agent runtime
# 都以類前綴格式繞過 lint：auto-commit / copilot-auto。把任何 `<agent>-<state>:`
# 形式的非語意前綴一律拒，迫使 agent 走 chore(auto-engineer) / chore(copilot)
# 等 Conventional Commit 形狀（contract 見 docs/commit-plan.md v4）。
_REJECT_PATTERNS = (
    re.compile(r"^auto-commit:\s*checkpoint", re.IGNORECASE),
    re.compile(r"^auto-commit:?\s*$", re.IGNORECASE),
    re.compile(r"^chore\(auto-engineer\):\s*checkpoint(?:\s+snapshot)?\b", re.IGNORECASE),
    re.compile(r"^chore\(auto-engineer\):\s*patch\b", re.IGNORECASE),
    re.compile(r"^copilot-auto:", re.IGNORECASE),  # Copilot batch round 違規
    re.compile(r"^[a-z]+-auto:", re.IGNORECASE),   # 通用 <agent>-auto: 兜底
    re.compile(r"^WIP\s*$", re.IGNORECASE),
    re.compile(r"^(fix|update|change|tmp|temp|misc)\s*$", re.IGNORECASE),
    re.compile(r"^checkpoint\s*$", re.IGNORECASE),
)

_MIN_SUBJECT_LEN = 10


def _read_message(arg: str) -> str:
    if arg == "-":
        return sys.stdin.read()
    return Path(arg).read_text(encoding="utf-8")


def lint(message: str) -> tuple[bool, str]:
    """Return (is_valid, reason).

    ``reason`` is a human-readable explanation of why the message was rejected,
    or an empty string when the message is accepted.
    """
    # First non-empty, non-comment line is the header
    header = ""
    for raw in message.splitlines():
        line = raw.rstrip()
        if not line or line.startswith("#"):
            continue
        header = line
        break

    if not header:
        return False, "commit message is empty"

    for pat in _REJECT_PATTERNS:
        if pat.match(header):
            return False, (
                f"naked / lazy commit subject rejected: {header!r}\n"
                "  Use a semantic prefix (feat/fix/refactor/docs/chore/test/perf/...) "
                "and describe WHY the change was made."
            )

    match = _HEADER_RE.match(header)
    if not match:
        return False, (
            f"missing Conventional Commit prefix: {header!r}\n"
            f"  Expected: <type>(optional-scope): <subject>\n"
            f"  Allowed types: {', '.join(_ALLOWED_TYPES)}"
        )

    subject = match.group("subject").strip()
    if len(subject) < _MIN_SUBJECT_LEN:
        return False, (
            f"subject too short ({len(subject)} chars < {_MIN_SUBJECT_LEN}): {subject!r}\n"
            "  Describe what changed and (briefly) why — placeholders like "
            "'fix bug' or 'update' are not enough."
        )

    return True, ""


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: commit_msg_lint.py <commit-msg-file|->", file=sys.stderr)
        return 2

    try:
        message = _read_message(argv[1])
    except FileNotFoundError as exc:
        print(f"commit-msg file not found: {exc}", file=sys.stderr)
        return 2

    ok, reason = lint(message)
    if ok:
        return 0
    print(f"[commit-msg-lint] REJECTED:\n  {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
