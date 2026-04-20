from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from src.integrations.open_notebook import IntegrationDisabled, IntegrationSetupError
from src.integrations.open_notebook.service import (
    OpenNotebookAskRequest,
    OpenNotebookService,
)
from src.integrations.open_notebook.stub import AskResult, RetrievedEvidence


@dataclass
class RecordingAdapter:
    seen_question: str | None = None
    seen_docs: list[dict[str, object]] | None = None

    def ask(self, question: str, docs: list[dict[str, object]] | None = None) -> AskResult:
        self.seen_question = question
        self.seen_docs = list(docs or [])
        return AskResult(
            answer_text="adapter-answer",
            evidence=[RetrievedEvidence(title="doc-1", snippet="snippet", rank=1)],
            diagnostics={"adapter": "recording"},
        )

    def index(self, docs: list[dict[str, object]]) -> int:
        return len(docs)


def test_service_passes_request_to_repo_owned_adapter() -> None:
    adapter = RecordingAdapter()
    service = OpenNotebookService(adapter=adapter, mode="writer")
    request = OpenNotebookAskRequest(
        question="how",
        docs=(
            {"title": "Doc 1", "content_md": "alpha"},
            {"title": "Doc 2", "content_md": "beta"},
        ),
        top_k=1,
        trace_id="trace-123",
        metadata_filters={"agency": "epa", "doc_type": "函"},
    )

    result = service.ask(request)

    assert adapter.seen_question == "how"
    assert adapter.seen_docs == [{"title": "Doc 1", "content_md": "alpha"}]
    assert result.answer_text == "adapter-answer"
    assert result.diagnostics["adapter"] == "recording"
    assert result.diagnostics["service"] == "open-notebook"
    assert result.diagnostics["mode"] == "writer"
    assert result.diagnostics["trace_id"] == "trace-123"
    assert result.diagnostics["metadata_filters"] == "agency=epa,doc_type=函"


def test_service_uses_smoke_mode_from_runtime_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "smoke")
    service = OpenNotebookService()

    result = service.ask(
        OpenNotebookAskRequest(
            question="hi",
            docs=({"title": "Doc A", "content_md": "alpha"},),
        )
    )

    assert result.answer_text.startswith("[open-notebook smoke] hi")
    assert result.evidence[0].title == "Doc A"
    assert result.diagnostics["adapter"] == "smoke"
    assert result.diagnostics["service"] == "open-notebook"
    assert result.diagnostics["mode"] == "env"


def test_service_off_mode_preserves_legacy_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "off")
    service = OpenNotebookService()

    with pytest.raises(IntegrationDisabled):
        service.ask(OpenNotebookAskRequest(question="hi"))


def test_service_writer_mode_fails_loudly_without_vendor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    vendor_path = tmp_path / "open-notebook"
    (vendor_path / ".git").mkdir(parents=True)
    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "writer")
    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_VENDOR_PATH", str(vendor_path))
    service = OpenNotebookService()

    with pytest.raises(IntegrationSetupError) as exc_info:
        service.ask(OpenNotebookAskRequest(question="hi"))

    assert "writer mode requires a usable vendor/open-notebook checkout" in str(exc_info.value)
    assert "only .git metadata" in str(exc_info.value)
