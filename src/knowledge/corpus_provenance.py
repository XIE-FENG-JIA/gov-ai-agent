from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml


def read_markdown_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    """Read YAML frontmatter plus body from a markdown file."""
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        return {}, raw

    parts = raw.split("---\n", 2)
    if len(parts) < 3:
        return {}, raw

    metadata = yaml.safe_load(parts[1]) or {}
    if not isinstance(metadata, dict):
        return {}, parts[2].strip()
    return metadata, parts[2].strip()


def is_fixture_backed_metadata(metadata: Mapping[str, Any] | None) -> bool:
    meta = metadata or {}
    return bool(meta.get("synthetic") or meta.get("fixture_fallback"))


def is_active_corpus_metadata(metadata: Mapping[str, Any] | None) -> bool:
    meta = metadata or {}
    if bool(meta.get("deprecated")):
        return False
    return not is_fixture_backed_metadata(meta)
