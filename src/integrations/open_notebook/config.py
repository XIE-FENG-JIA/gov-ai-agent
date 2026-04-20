"""Configuration helpers for the open-notebook integration seam."""

from __future__ import annotations

import os


OPEN_NOTEBOOK_MODE_ENV = "GOV_AI_OPEN_NOTEBOOK_MODE"
_VALID_MODES = {"off", "smoke", "writer"}


def get_open_notebook_mode(explicit_mode: str | None = None) -> str:
    """Return a normalized runtime mode for the open-notebook seam."""
    raw_mode = (explicit_mode if explicit_mode is not None else os.getenv(OPEN_NOTEBOOK_MODE_ENV, "off")).strip().lower()
    if raw_mode not in _VALID_MODES:
        valid = ", ".join(sorted(_VALID_MODES))
        raise ValueError(f"Unsupported {OPEN_NOTEBOOK_MODE_ENV} mode: {raw_mode!r}. Expected one of: {valid}")
    return raw_mode

