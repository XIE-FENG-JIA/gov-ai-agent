from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.agents.writer import WriterAgent
from src.core.models import PublicDocRequirement
from src.integrations.open_notebook import IntegrationSetupError
from src.integrations.open_notebook.service import OpenNotebookAskRequest
from src.integrations.open_notebook.stub import AskResult


def _requirement() -> PublicDocRequirement:
    return PublicDocRequirement(
        doc_type="函",
        sender="環境部",
        receiver="各地方政府",
        subject="加強資源回收宣導",
        reason="依上級政策辦理",
        action_items=["請於期限內完成宣導"],
        attachments=["宣導計畫"],
    )


def _example() -> dict:
    return {
        "id": "kb-1",
        "content": "依據行政院核定方案辦理。",
        "distance": 0.2,
        "metadata": {
            "title": "環保政策範例",
            "source_level": "A",
            "source_url": "https://example.test/doc-1",
            "source": "law",
            "meta_id": "doc-1",
        },
    }


def _legacy_writer() -> MagicMock:
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "### 主旨\nlegacy 草稿\n\n### 說明\n依據行政院核定方案辦理。"
    return mock_llm


def _kb_with_examples() -> MagicMock:
    mock_kb = MagicMock()
    mock_kb.search_hybrid.return_value = [_example()]
    return mock_kb


def test_writer_failure_matrix_records_setup_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "writer")
    mock_llm = _legacy_writer()
    mock_kb = _kb_with_examples()

    class SetupFailingService:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def ask(self, request: OpenNotebookAskRequest) -> AskResult:
            raise IntegrationSetupError("vendor path missing")

    monkeypatch.setattr("src.agents.writer.OpenNotebookService", SetupFailingService)
    writer = WriterAgent(mock_llm, mock_kb)

    draft = writer.write_draft(_requirement())

    assert "legacy 草稿" in draft
    assert writer._last_open_notebook_diagnostics == {
        "service": "open-notebook",
        "mode": "writer",
        "used_fallback": "true",
        "fallback_stage": "setup",
        "fallback_reason": "vendor path missing",
    }
    mock_llm.generate.assert_called_once()


def test_writer_failure_matrix_records_runtime_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "smoke")
    mock_llm = _legacy_writer()
    mock_kb = _kb_with_examples()

    class RuntimeFailingService:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def ask(self, request: OpenNotebookAskRequest) -> AskResult:
            raise RuntimeError("boom")

    monkeypatch.setattr("src.agents.writer.OpenNotebookService", RuntimeFailingService)
    writer = WriterAgent(mock_llm, mock_kb)

    draft = writer.write_draft(_requirement())

    assert "legacy 草稿" in draft
    assert writer._last_open_notebook_diagnostics == {
        "service": "open-notebook",
        "mode": "smoke",
        "used_fallback": "true",
        "fallback_stage": "runtime",
        "fallback_reason": "boom",
    }
    mock_llm.generate.assert_called_once()


def test_writer_failure_matrix_records_timeout_as_runtime_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "smoke")
    mock_llm = _legacy_writer()
    mock_kb = _kb_with_examples()

    class TimeoutService:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def ask(self, request: OpenNotebookAskRequest) -> AskResult:
            raise TimeoutError("service timed out")

    monkeypatch.setattr("src.agents.writer.OpenNotebookService", TimeoutService)
    writer = WriterAgent(mock_llm, mock_kb)

    draft = writer.write_draft(_requirement())

    assert "legacy 草稿" in draft
    assert writer._last_open_notebook_diagnostics == {
        "service": "open-notebook",
        "mode": "smoke",
        "used_fallback": "true",
        "fallback_stage": "runtime",
        "fallback_reason": "service timed out",
    }
    mock_llm.generate.assert_called_once()


def test_writer_failure_matrix_keeps_service_draft_when_retrieval_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "smoke")
    mock_llm = _legacy_writer()
    mock_kb = MagicMock()
    mock_kb.search_hybrid.return_value = []

    class EmptyRetrievalService:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def ask(self, request: OpenNotebookAskRequest) -> AskResult:
            assert request.docs == ()
            return AskResult(
                answer_text="### 主旨\nservice 草稿\n\n### 說明\n依據現況先行辦理。",
                evidence=[],
                diagnostics={"adapter": "writer", "fallback_reason": "retrieval empty"},
                used_fallback=True,
            )

    monkeypatch.setattr("src.agents.writer.OpenNotebookService", EmptyRetrievalService)
    writer = WriterAgent(mock_llm, mock_kb)

    draft = writer.write_draft(_requirement())

    assert "service 草稿" in draft
    assert "legacy 草稿" not in draft
    assert "骨架模式" in draft
    assert "### 參考來源 (AI 引用追蹤)" not in draft
    assert writer._last_open_notebook_diagnostics == {
        "adapter": "writer",
        "fallback_reason": "retrieval empty",
        "service": "open-notebook",
        "mode": "smoke",
        "used_fallback": "true",
        "fallback_stage": "service",
    }
