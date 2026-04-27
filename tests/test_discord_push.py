"""Tests for src.api.routes.workflow._discord_push (discord push helper)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.routes.workflow._discord_push import (
    _build_embed,
    _color_for,
    schedule_push,
)


# ---------------------------------------------------------------------------
# _color_for
# ---------------------------------------------------------------------------


def test_color_for_critical_risk() -> None:
    assert _color_for(None, "Critical") == 0xEF4444


def test_color_for_high_risk() -> None:
    assert _color_for(None, "High") == 0xF59E0B


def test_color_for_high_score() -> None:
    assert _color_for(0.9, None) == 0x10B981


def test_color_for_mid_score() -> None:
    assert _color_for(0.7, None) == 0xF59E0B


def test_color_for_low_score() -> None:
    assert _color_for(0.5, None) == 0xEF4444


def test_color_for_no_args() -> None:
    # None score, None risk → red
    assert _color_for(None, None) == 0xEF4444


# ---------------------------------------------------------------------------
# _build_embed
# ---------------------------------------------------------------------------


def test_build_embed_minimal() -> None:
    payload = _build_embed("sess-001", "小測試", None, None)
    embeds = payload["embeds"]
    assert len(embeds) == 1
    embed = embeds[0]
    assert "sess-001" in embed["title"]
    assert embed["description"] == "小測試"
    assert isinstance(embed["color"], int)
    field_names = [f["name"] for f in embed["fields"]]
    assert "加權總分" in field_names
    assert "風險等級" in field_names


def test_build_embed_with_list_agents() -> None:
    qa = {
        "overall_score": 0.88,
        "risk_summary": "Low",
        "rounds_used": 2,
        "agent_results": [
            {"agent": "Format Auditor", "score": 0.9, "issues": []},
            {"agent": "Fact Checker", "score": 0.75, "issues": [
                {"risk_level": "high", "description": "Missing citation", "location": "section 2"},
            ]},
        ],
    }
    payload = _build_embed("sess-002", "測試公文", "/tmp/out.docx", qa)
    embed = payload["embeds"][0]
    reviewer_field = next(f for f in embed["fields"] if "Reviewer" in f["name"])
    assert "Format Auditor" in reviewer_field["value"]
    assert "Fact Checker" in reviewer_field["value"]


def test_build_embed_with_dict_agents() -> None:
    qa = {
        "overall_score": 0.80,
        "agent_results": {
            "Style Checker": {"score": 0.82},
            "Compliance Checker": {"score": 0.78},
        },
    }
    payload = _build_embed("sess-003", "Dict agent test", None, qa)
    embed = payload["embeds"][0]
    reviewer_field = next(f for f in embed["fields"] if "Reviewer" in f["name"])
    assert "Style Checker" in reviewer_field["value"]


def test_build_embed_long_user_input_truncated() -> None:
    long_input = "A" * 200
    payload = _build_embed("sess-004", long_input, None, None)
    desc = payload["embeds"][0]["description"]
    assert len(desc) <= 120


# ---------------------------------------------------------------------------
# schedule_push — no running loop
# ---------------------------------------------------------------------------


def test_schedule_push_no_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """schedule_push must silently skip if event loop is not running."""
    mock_loop = MagicMock()
    mock_loop.is_running.return_value = False
    monkeypatch.setattr(asyncio, "get_event_loop", lambda: mock_loop)
    # Should not raise
    schedule_push("s1", "input", None, None)
    mock_loop.create_task.assert_not_called()


def test_schedule_push_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """schedule_push must silently skip on RuntimeError (no loop)."""
    monkeypatch.setattr(asyncio, "get_event_loop", lambda: (_ for _ in ()).throw(RuntimeError("no loop")))
    # Should not raise
    schedule_push("s2", "input", None, None)


def test_schedule_push_creates_task_when_loop_running(monkeypatch: pytest.MonkeyPatch) -> None:
    """schedule_push creates an asyncio task when loop is running."""
    created_coros: list = []

    def capture_task(coro):
        created_coros.append(coro)
        return MagicMock()

    mock_loop = MagicMock()
    mock_loop.is_running.return_value = True
    mock_loop.create_task = capture_task
    monkeypatch.setattr(asyncio, "get_event_loop", lambda: mock_loop)
    schedule_push("s3", "meeting input", "/out.docx", {"overall_score": 0.9})
    assert len(created_coros) == 1
    # Close the coroutine to avoid RuntimeWarning
    created_coros[0].close()
