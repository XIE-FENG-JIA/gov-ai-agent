from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Mapping, Sequence

from . import get_adapter
from .stub import AskResult

if TYPE_CHECKING:
    from . import OpenNotebookAdapter


@dataclass(frozen=True)
class OpenNotebookAskRequest:
    """Repo-owned ask contract for the open-notebook seam."""

    question: str
    docs: Sequence[Mapping[str, object]] = field(default_factory=tuple)
    top_k: int = 5
    trace_id: str | None = None
    metadata_filters: Mapping[str, str] | None = None


class OpenNotebookService:
    """Thin repo-owned service adapter for ask-style calls."""

    def __init__(
        self,
        adapter: OpenNotebookAdapter | None = None,
        *,
        mode: str | None = None,
    ) -> None:
        self._adapter = adapter
        self._mode = mode

    def ask(self, request: OpenNotebookAskRequest) -> AskResult:
        adapter = self._adapter or get_adapter(self._mode)
        docs = list(request.docs[: max(request.top_k, 0)])
        result = adapter.ask(request.question, docs)

        diagnostics = dict(result.diagnostics)
        diagnostics.setdefault("service", "open-notebook")
        diagnostics.setdefault("mode", self._mode or "env")
        if request.trace_id:
            diagnostics["trace_id"] = request.trace_id
        if request.metadata_filters:
            diagnostics["metadata_filters"] = self._serialize_filters(request.metadata_filters)

        return AskResult(
            answer_text=result.answer_text,
            evidence=result.evidence,
            diagnostics=diagnostics,
            used_fallback=result.used_fallback,
        )

    @staticmethod
    def _serialize_filters(metadata_filters: Mapping[str, str]) -> str:
        return ",".join(
            f"{key}={value}"
            for key, value in sorted(metadata_filters.items())
        )


__all__ = ["OpenNotebookAskRequest", "OpenNotebookService"]
