#!/usr/bin/env python3
"""Audit kb_data/examples/ files for YAML frontmatter synthetic flag.

Every file is expected to have ``synthetic: true`` or ``synthetic: false``
in its YAML frontmatter block (between the opening and closing ``---``).

Usage::

    python scripts/audit_synthetic_flag.py                  # report only
    python scripts/audit_synthetic_flag.py --strict         # exit 1 if any missing
    python scripts/audit_synthetic_flag.py --path kb_data/examples --strict

Exit 0 = all files tagged (or reporting-only mode).
Exit 1 = untagged files found (when --strict).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Matches either:
#   synthetic: true
#   synthetic: false
#   synthetic: "true"   etc.
_SYNTHETIC_RE = re.compile(r"^\s*synthetic\s*:", re.MULTILINE)

# YAML frontmatter delimiters
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _has_synthetic_tag(text: str) -> bool:
    """Return True if the file's YAML frontmatter contains a 'synthetic:' key."""
    fm_match = _FRONTMATTER_RE.match(text)
    if not fm_match:
        # No frontmatter at all → not tagged
        return False
    return bool(_SYNTHETIC_RE.search(fm_match.group(1)))


def audit_directory(root: Path, extensions: tuple[str, ...] = (".md",)) -> tuple[list[Path], list[Path]]:
    """Scan *root* recursively.

    Returns (tagged, untagged) lists of Path objects.
    """
    tagged: list[Path] = []
    untagged: list[Path] = []

    for path in sorted(root.rglob("*")):
        if path.suffix not in extensions or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"WARN: cannot read {path}: {exc}", file=sys.stderr)
            untagged.append(path)
            continue
        if _has_synthetic_tag(text):
            tagged.append(path)
        else:
            untagged.append(path)

    return tagged, untagged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        default="kb_data/examples",
        help="Directory to audit (default: kb_data/examples)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any files are missing the synthetic flag.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-file output; only print summary.",
    )
    args = parser.parse_args(argv)

    root = Path(args.path)
    if not root.is_dir():
        print(f"ERROR: {root} is not a directory.", file=sys.stderr)
        return 2

    tagged, untagged = audit_directory(root)
    total = len(tagged) + len(untagged)

    if untagged and not args.quiet:
        print(f"\nFiles missing 'synthetic:' tag ({len(untagged)}/{total}):")
        for p in untagged:
            print(f"  MISSING  {p}")

    print(
        f"\n[audit_synthetic_flag] {len(tagged)}/{total} tagged"
        + (" ✓" if not untagged else f" — {len(untagged)} untagged")
    )

    if untagged and args.strict:
        print("[audit_synthetic_flag] FAIL (--strict)", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
