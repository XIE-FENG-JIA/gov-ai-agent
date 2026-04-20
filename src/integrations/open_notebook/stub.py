from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence


class IntegrationDisabled(RuntimeError):
    """Raised when the integration seam is explicitly disabled."""


class IntegrationSetupError(RuntimeError):
    """Raised when the vendored runtime is not available or not ready."""


@dataclass(frozen=True)
class RetrievedEvidence:
    title: str
    snippet: str
    source_url: str = ""
    rank: int | None = None


@dataclass(frozen=True)
class AskResult:
    answer_text: str
    evidence: list[RetrievedEvidence] = field(default_factory=list)
    diagnostics: dict[str, str] = field(default_factory=dict)
    used_fallback: bool = False


class OffAdapter:
    """Hard-off adapter that keeps the legacy path as the default."""

    def ask(
        self,
        question: str,
        docs: Sequence[Mapping[str, object]] | None = None,
    ) -> AskResult:
        raise IntegrationDisabled(
            "open-notebook integration is disabled; set GOV_AI_OPEN_NOTEBOOK_MODE=smoke "
            "for the smoke path or writer after the vendor runtime is wired"
        )

    def index(self, docs: Sequence[Mapping[str, object]]) -> int:
        return len(docs)


class SmokeAdapter:
    """In-memory smoke adapter used before the vendored runtime is wired."""

    def ask(
        self,
        question: str,
        docs: Sequence[Mapping[str, object]] | None = None,
    ) -> AskResult:
        evidence = [self._to_evidence(index, doc) for index, doc in enumerate(docs or (), start=1)]
        if not evidence:
            evidence = [RetrievedEvidence(title="smoke-input", snippet=question, rank=1)]

        primary = evidence[0]
        answer = (
            f"[open-notebook smoke] {question}\n"
            f"evidence: {primary.title}"
        )
        diagnostics = {
            "adapter": "smoke",
            "evidence_count": str(len(evidence)),
        }
        return AskResult(answer_text=answer, evidence=evidence, diagnostics=diagnostics)

    def index(self, docs: Sequence[Mapping[str, object]]) -> int:
        return len(docs)

    @staticmethod
    def _to_evidence(index: int, doc: Mapping[str, object]) -> RetrievedEvidence:
        title = str(doc.get("title") or doc.get("source_id") or f"doc-{index}")
        snippet = str(
            doc.get("snippet")
            or doc.get("content_md")
            or doc.get("content")
            or ""
        ).strip()
        source_url = str(doc.get("source_url") or "")
        if not snippet:
            snippet = title
        return RetrievedEvidence(
            title=title,
            snippet=snippet,
            source_url=source_url,
            rank=index,
        )
