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
        "feat(cli): add /v2/refine command",
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
        ("chore(auto-engineer): checkpoint snapshot (2026-04-25 18:17:35 +0800) @ 2026-04-25 18:19", "semantic-looking checkpoint noise"),
        ("chore(auto-engineer): patch", "semantic-looking patch noise"),
        ("chore(copilot): batch round 17 (2026-04-26 00:02:55 +0800)", "semantic-looking copilot batch noise"),
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


@pytest.mark.parametrize(
    "msg",
    [
        "feat(llm): route OpenRouter embeddings through REST\n\npytest tests/test_llm.py = 52 passed\n",
        "feat(core): add history store append contract\n\npytest tests/test_core.py = 117 passed\n",
        "feat(api): validate uploaded document MIME type\n\npytest tests/test_api_server.py = 259 passed\n",
    ],
)
def test_high_risk_feat_scopes_accept_same_scope_pytest_evidence(msg: str) -> None:
    ok, reason = lint(msg)
    assert ok, reason


@pytest.mark.parametrize(
    "msg, expected",
    [
        ("feat(llm): route OpenRouter embeddings through REST", "tests/test_llm.py"),
        ("feat(core): add history store append contract\n\npytest tests/test_llm.py = 52 passed\n", "tests/test_core.py"),
        ("feat(api): validate uploaded document MIME type\n\npytest tests/test_api_server.py passed\n", "tests/test_api_server.py"),
        ("feat(api): validate uploaded document MIME type\n\npytest tests/test_api_server.py = 0 passed\n", "tests/test_api_server.py"),
        ("feat(llm): route OpenRouter embeddings through REST\n\npytest tests/test_llm.py = 52 failed\n", "tests/test_llm.py"),
    ],
)
def test_high_risk_feat_scopes_require_counted_same_scope_pytest_evidence(msg: str, expected: str) -> None:
    ok, reason = lint(msg)
    assert not ok
    assert expected in reason
