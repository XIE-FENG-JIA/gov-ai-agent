from __future__ import annotations

from pathlib import Path
from typing import Mapping, Protocol, Sequence, runtime_checkable

from .config import (
    get_open_notebook_mode,
    get_open_notebook_vendor_path,
    normalize_open_notebook_mode,
)
from .stub import (
    AskResult,
    IntegrationDisabled,
    IntegrationSetupError,
    OffAdapter,
    RetrievedEvidence,
    SmokeAdapter,
)


@runtime_checkable
class OpenNotebookAdapter(Protocol):
    """Repo-owned adapter contract for ask/index entrypoints."""

    def ask(
        self,
        question: str,
        docs: Sequence[Mapping[str, object]] | None = None,
    ) -> AskResult:
        ...

    def index(self, docs: Sequence[Mapping[str, object]]) -> int:
        ...


def probe_vendor_runtime(vendor_path: Path | None = None) -> tuple[bool, str]:
    """Check whether the vendored runtime looks like a checked-out Python project."""
    path = vendor_path or get_open_notebook_vendor_path()
    if not path.exists():
        return False, f"vendor path does not exist: {path}"

    entries = [entry for entry in path.iterdir() if entry.name != ".git"]
    if not entries:
        return False, f"vendor path has only .git metadata and no checked-out files: {path}"

    has_python_project = any(
        candidate.exists()
        for candidate in (
            path / "pyproject.toml",
            path / "setup.py",
            path / "open_notebook",
            path / "src",
        )
    )
    if not has_python_project:
        return False, f"vendor path does not contain an importable Python project: {path}"

    return True, "ok"


def get_adapter(mode: str | None = None) -> OpenNotebookAdapter:
    """Resolve the adapter by explicit mode or environment."""
    resolved_mode = normalize_open_notebook_mode(mode) if mode is not None else get_open_notebook_mode()
    if resolved_mode == "off":
        return OffAdapter()
    if resolved_mode == "smoke":
        return SmokeAdapter()

    is_ready, reason = probe_vendor_runtime()
    if not is_ready:
        raise IntegrationSetupError(
            "writer mode requires a usable vendor/open-notebook checkout; "
            f"{reason}"
        )
    raise IntegrationSetupError(
        "writer mode is reserved until the vendored open-notebook runtime is wired "
        "through the repo-owned service adapter"
    )


__all__ = [
    "AskResult",
    "IntegrationDisabled",
    "IntegrationSetupError",
    "OpenNotebookAdapter",
    "RetrievedEvidence",
    "get_adapter",
    "probe_vendor_runtime",
]
