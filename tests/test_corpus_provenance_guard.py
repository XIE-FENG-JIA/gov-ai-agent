from __future__ import annotations

from pathlib import Path

import yaml


def _read_frontmatter(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    assert raw.startswith("---\n"), f"{path} missing frontmatter"
    parts = raw.split("---\n", 2)
    assert len(parts) >= 3, f"{path} has malformed frontmatter"
    meta = yaml.safe_load(parts[1]) or {}
    assert isinstance(meta, dict), f"{path} frontmatter must be a mapping"
    return meta


def test_corpus_provenance_guard() -> None:
    corpus_root = Path("kb_data") / "corpus"
    corpus_files = sorted(corpus_root.rglob("*.md"))

    assert len(corpus_files) >= 9, "expected at least 9 real corpus files"

    synthetic_paths: list[str] = []
    fixture_fallback_paths: list[str] = []

    for path in corpus_files:
        meta = _read_frontmatter(path)
        if bool(meta.get("synthetic")):
            synthetic_paths.append(path.as_posix())
        if bool(meta.get("fixture_fallback")):
            fixture_fallback_paths.append(path.as_posix())

    assert not synthetic_paths, f"synthetic corpus files found: {synthetic_paths}"
    assert not fixture_fallback_paths, f"fixture-backed corpus files found: {fixture_fallback_paths}"
