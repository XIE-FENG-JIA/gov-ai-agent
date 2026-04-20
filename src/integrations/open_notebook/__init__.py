"""Repo-owned seam for the vendored open-notebook runtime."""

from .config import OPEN_NOTEBOOK_MODE_ENV, get_open_notebook_mode
from .stub import (
    AskResult,
    EvidenceItem,
    IntegrationDisabled,
    OpenNotebookAdapter,
    OffAdapter,
    SmokeAdapter,
    WriterAdapter,
    get_adapter,
)

__all__ = [
    "AskResult",
    "EvidenceItem",
    "IntegrationDisabled",
    "OPEN_NOTEBOOK_MODE_ENV",
    "OffAdapter",
    "OpenNotebookAdapter",
    "SmokeAdapter",
    "WriterAdapter",
    "get_adapter",
    "get_open_notebook_mode",
]

