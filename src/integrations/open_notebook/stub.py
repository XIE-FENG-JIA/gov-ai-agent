"""Minimal repo-owned open-notebook seam used before vendor runtime wiring."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .config import get_open_notebook_mode


@dataclass(frozen=True)
class EvidenceItem:
    """Stable evidence payload preserved for downstream review code."""

    title: str
    snippet: str
    source_url: str = ""
    source_type: str = "local"
    score: float | None = None


@dataclass(frozen=True)
class AskResult:
    """Repo-owned ask-style response contract."""

    answer: str
    citations: list[EvidenceItem]
    mode: str
    diagnostics: dict[str, str]


class IntegrationDisabled(RuntimeError):
    """Raised when the requested integration mode is unavailable."""


class OpenNotebookAdapter(Protocol):
    """Repo-owned adapter seam for ask-style calls."""

    mode: str

    def index(self, docs: list[str]) -> int:
        """Index a set of docs into the adapter's runtime."""

    def ask(self, question: str, docs: list[str]) -> AskResult:
        """Answer a question while preserving evidence payloads."""


class OffAdapter:
    """Disabled mode that fails explicitly instead of silently falling back."""

    mode = "off"

    def index(self, docs: list[str]) -> int:
        return 0

    def ask(self, question: str, docs: list[str]) -> AskResult:
        raise IntegrationDisabled("open-notebook integration is disabled; set GOV_AI_OPEN_NOTEBOOK_MODE=smoke or writer")


class SmokeAdapter:
    """Deterministic in-memory adapter used for seam verification only."""

    mode = "smoke"

    def index(self, docs: list[str]) -> int:
        return len([doc for doc in docs if doc.strip()])

    def ask(self, question: str, docs: list[str]) -> AskResult:
        normalized_docs = [doc.strip() for doc in docs if doc.strip()]
        if not normalized_docs:
            normalized_docs = ["No source document supplied."]

        primary_doc = normalized_docs[0]
        evidence = EvidenceItem(
            title="smoke-doc-1",
            snippet=primary_doc[:160],
            source_type="smoke",
            score=1.0,
        )
        answer = f"[smoke] {question.strip() or 'No question provided.'} | evidence: {primary_doc[:80]}"
        return AskResult(
            answer=answer,
            citations=[evidence],
            mode=self.mode,
            diagnostics={"indexed_docs": str(len(normalized_docs))},
        )


class WriterAdapter:
    """Placeholder for future vendor-backed writer mode."""

    mode = "writer"

    def __init__(self, vendor_path: Path | None = None) -> None:
        self.vendor_path = vendor_path or Path("vendor/open-notebook")

    def index(self, docs: list[str]) -> int:
        self._raise_missing_vendor()

    def ask(self, question: str, docs: list[str]) -> AskResult:
        self._raise_missing_vendor()

    def _raise_missing_vendor(self) -> None:
        raise IntegrationDisabled(
            "open-notebook writer mode is unavailable because the vendor runtime is not ready: "
            f"{self.vendor_path.as_posix()}"
        )


def get_adapter(mode: str | None = None) -> OpenNotebookAdapter:
    """Return the repo-owned adapter matching the requested mode."""
    normalized_mode = get_open_notebook_mode(mode)
    if normalized_mode == "off":
        return OffAdapter()
    if normalized_mode == "smoke":
        return SmokeAdapter()
    return WriterAdapter()

