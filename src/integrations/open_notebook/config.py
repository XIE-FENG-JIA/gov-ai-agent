from __future__ import annotations

import os
from pathlib import Path


OPEN_NOTEBOOK_MODE_ENV = "GOV_AI_OPEN_NOTEBOOK_MODE"
OPEN_NOTEBOOK_VENDOR_PATH_ENV = "GOV_AI_OPEN_NOTEBOOK_VENDOR_PATH"
VALID_OPEN_NOTEBOOK_MODES = ("off", "smoke", "writer")


def normalize_open_notebook_mode(mode: str | None) -> str:
    """Normalize and validate the open-notebook runtime mode."""
    normalized = (mode or "off").strip().lower() or "off"
    if normalized not in VALID_OPEN_NOTEBOOK_MODES:
        allowed = ", ".join(VALID_OPEN_NOTEBOOK_MODES)
        raise ValueError(f"invalid open-notebook mode: {normalized!r}; expected one of {allowed}")
    return normalized


def get_open_notebook_mode() -> str:
    """Read the runtime mode from the environment."""
    return normalize_open_notebook_mode(os.getenv(OPEN_NOTEBOOK_MODE_ENV, "off"))


def get_open_notebook_vendor_path() -> Path:
    """Resolve the vendored runtime path."""
    raw = os.getenv(OPEN_NOTEBOOK_VENDOR_PATH_ENV, "").strip()
    return Path(raw) if raw else Path("vendor") / "open-notebook"
