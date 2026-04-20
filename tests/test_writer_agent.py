from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.agents.writer import WriterAgent
from src.core.models import PublicDocRequirement
from src.integrations.open_notebook.service import OpenNotebookAskRequest
from src.integrations.open_notebook.stub import AskResult, RetrievedEvidence


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


def test_writer_uses_legacy_llm_when_open_notebook_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "off")
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "### 主旨\n加強資源回收宣導\n\n### 說明\n依據行政院核定方案辦理。"
    mock_kb = MagicMock()
    mock_kb.search_hybrid.return_value = [_example()]
    writer = WriterAgent(mock_llm, mock_kb)

    draft = writer.write_draft(_requirement())

    assert "### 參考來源 (AI 引用追蹤)" in draft
    mock_llm.generate.assert_called_once()


def test_writer_uses_open_notebook_service_when_toggle_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "smoke")
    mock_llm = MagicMock()
    mock_kb = MagicMock()
    mock_kb.search_hybrid.return_value = [_example()]

    captured: dict[str, object] = {}

    class FakeService:
        def __init__(self, *args, **kwargs) -> None:
            captured["mode"] = kwargs.get("mode")

        def ask(self, request: OpenNotebookAskRequest) -> AskResult:
            captured["request"] = request
            return AskResult(
                answer_text="### 主旨\nsmoke 草稿\n\n### 說明\n依據行政院核定方案辦理。",
                evidence=[
                    RetrievedEvidence(
                        title="環保政策範例",
                        snippet="依據行政院核定方案辦理。",
                        source_url="https://example.test/doc-1",
                        rank=1,
                    )
                ],
                diagnostics={"adapter": "smoke"},
            )

    monkeypatch.setattr("src.agents.writer.OpenNotebookService", FakeService)
    writer = WriterAgent(mock_llm, mock_kb)

    draft = writer.write_draft(_requirement())

    assert "smoke 草稿" in draft
    assert "### 參考來源 (AI 引用追蹤)" in draft
    assert captured["mode"] == "smoke"
    request = captured["request"]
    assert isinstance(request, OpenNotebookAskRequest)
    assert request.metadata_filters == {"doc_type": "函"}
    assert request.docs[0]["title"] == "環保政策範例"
    mock_llm.generate.assert_not_called()


def test_writer_references_open_notebook_retrieved_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "smoke")
    mock_llm = MagicMock()
    mock_kb = MagicMock()
    mock_kb.search_hybrid.return_value = [_example()]

    class FakeService:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def ask(self, request: OpenNotebookAskRequest) -> AskResult:
            return AskResult(
                answer_text="### 主旨\nsmoke 草稿\n\n### 說明\n一、依據行政院核定方案辦理[^1]。",
                evidence=[
                    RetrievedEvidence(
                        title="open-notebook 命中證據",
                        snippet="依據行政院核定方案辦理。",
                        source_url="https://example.test/retrieved",
                        rank=1,
                    )
                ],
                diagnostics={"adapter": "smoke"},
            )

    monkeypatch.setattr("src.agents.writer.OpenNotebookService", FakeService)
    writer = WriterAgent(mock_llm, mock_kb)

    draft = writer.write_draft(_requirement())

    assert "open-notebook 命中證據" in draft
    assert "https://example.test/retrieved" in draft
    assert "https://example.test/doc-1" not in draft
    assert writer._last_sources_list[0]["evidence_snippet"] == "依據行政院核定方案辦理。"
    mock_llm.generate.assert_not_called()


def test_writer_falls_back_to_legacy_llm_when_open_notebook_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "smoke")
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "### 主旨\nlegacy 草稿\n\n### 說明\n依據行政院核定方案辦理。"
    mock_kb = MagicMock()
    mock_kb.search_hybrid.return_value = [_example()]

    class ExplodingService:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def ask(self, request: OpenNotebookAskRequest) -> AskResult:
            raise RuntimeError("boom")

    monkeypatch.setattr("src.agents.writer.OpenNotebookService", ExplodingService)
    writer = WriterAgent(mock_llm, mock_kb)

    draft = writer.write_draft(_requirement())

    assert "legacy 草稿" in draft
    assert writer._last_open_notebook_diagnostics["used_fallback"] == "true"
    assert writer._last_open_notebook_diagnostics["fallback_stage"] == "runtime"
    assert writer._last_open_notebook_diagnostics["fallback_reason"] == "boom"
    mock_llm.generate.assert_called_once()


def test_writer_records_setup_fallback_when_open_notebook_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "writer")
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "### 主旨\nlegacy 草稿\n\n### 說明\n依據行政院核定方案辦理。"
    mock_kb = MagicMock()
    mock_kb.search_hybrid.return_value = [_example()]

    class SetupFailingService:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def ask(self, request: OpenNotebookAskRequest) -> AskResult:
            from src.integrations.open_notebook import IntegrationSetupError

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
