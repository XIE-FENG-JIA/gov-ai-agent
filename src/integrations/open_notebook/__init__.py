from __future__ import annotations

import importlib
from pathlib import Path
import sys
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


def _probe_git_stub(path: Path) -> tuple[bool, str] | None:
    git_dir = path / ".git"
    if not git_dir.is_dir():
        return None

    git_entries = {entry.name for entry in git_dir.iterdir()}
    if not git_entries:
        return None
    required_entries = ("HEAD", "config", "objects", "refs")
    missing_entries = [entry for entry in required_entries if entry not in git_entries]
    if not missing_entries:
        return None

    visible_entries = ", ".join(sorted(git_entries)) or "<empty>"
    missing_text = ", ".join(missing_entries)
    return (
        False,
        "vendor checkout is incomplete: "
        f".git contains [{visible_entries}] but is missing [{missing_text}] under {path}",
    )


def _candidate_sys_paths(path: Path) -> list[str]:
    entries: list[str] = []
    for candidate in (path, path / "src"):
        if candidate.exists():
            entries.append(str(candidate))
    return entries


def _probe_importable_project(path: Path) -> tuple[bool, str]:
    module_name = "open_notebook"
    candidate_entries = _candidate_sys_paths(path)
    module = None
    original_module = sys.modules.pop(module_name, None)
    original_sys_path = list(sys.path)
    sys.path[:0] = candidate_entries
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        missing = f" missing={exc.name}" if getattr(exc, "name", None) else ""
        return False, f"vendor runtime import failed: {type(exc).__name__}: {exc}.{missing}".rstrip()
    finally:
        sys.path[:] = original_sys_path
        sys.modules.pop(module_name, None)
        if original_module is not None:
            sys.modules[module_name] = original_module

    version = str(getattr(module, "__version__", "?"))
    origin = str(getattr(module, "__file__", ""))
    return True, f"imported open_notebook successfully version={version} origin={origin}"


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
        git_stub_probe = _probe_git_stub(path)
        if git_stub_probe is not None:
            return git_stub_probe
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

    return _probe_importable_project(path)


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
