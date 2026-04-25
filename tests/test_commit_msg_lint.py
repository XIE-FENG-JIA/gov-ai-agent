"""Tests for scripts/commit_msg_lint.py."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "commit_msg_lint.py"
_spec = importlib.util.spec_from_file_location("commit_msg_lint", _MODULE_PATH)
assert _spec and _spec.loader
_lint_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_lint_mod)
lint = _lint_mod.lint


@pytest.mark.parametrize(
    "msg",
    [
        "feat(api): add /v2/refine endpoint",
        "fix(cli): handle missing config gracefully when LLM_API_KEY absent",
        "refactor(monolith→package): split fact_checker into checks + pipeline",
        "docs(spec): 01-real-sources add specs/sources + tasks.md",
        "chore(cleanup): T9.5 root .ps1 归位 scripts/legacy",
        "feat!: drop legacy v1 endpoint",
        "test(adapter): cover MohwRssAdapter timeout path",
    ],
)
def test_accepts_semantic_messages(msg: str) -> None:
    ok, reason = lint(msg)
    assert ok, f"expected accept but got rejected: {reason!r}"


@pytest.mark.parametrize(
    "msg, why",
    [
        ("auto-commit: checkpoint (2026-04-22 04:19:55) @ 2026-04-22 04:29", "naked auto-commit checkpoint"),
        ("auto-commit:", "bare auto-commit prefix"),
        ("copilot-auto: batch round 2 (2026-04-25 05:30:00) @ 05:34", "copilot-auto batch prefix"),
        ("github-auto: nightly batch", "generic <agent>-auto: prefix"),
        ("WIP", "WIP placeholder"),
        ("fix", "single word"),
        ("update", "single word"),
        ("checkpoint", "checkpoint placeholder"),
        ("misc cleanup", "missing semantic prefix"),
        ("Add new feature", "no Conventional prefix"),
        ("feat: too short", "subject < 10 chars"),
    ],
)
def test_rejects_lazy_or_invalid_messages(msg: str, why: str) -> None:
    ok, reason = lint(msg)
    assert not ok, f"expected reject ({why}) but got accepted"
    assert reason, f"reject must include reason; got empty for {msg!r}"


def test_empty_message_rejected() -> None:
    ok, reason = lint("")
    assert not ok
    assert "empty" in reason


def test_comment_only_message_rejected() -> None:
    ok, reason = lint("# please enter a commit message\n# Lines starting with # are ignored\n")
    assert not ok
    assert "empty" in reason


def test_multiline_with_body_accepted() -> None:
    msg = (
        "feat(integration): add open-notebook service adapter\n"
        "\n"
        "Wraps vendored runtime imports behind one module so writer agents\n"
        "can opt in via feature flag. Falls back to legacy LLM path on error.\n"
    )
    ok, reason = lint(msg)
    assert ok, reason
