#!/usr/bin/env python3
"""Mark synthetic example markdown files with a YAML frontmatter flag."""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXAMPLES_DIR = ROOT / "kb_data" / "examples"
FRONTMATTER_RE = re.compile(r"^(---\s*\n)(.*?)(\n---\s*(?:\n|$))(.*)$", re.DOTALL)


@dataclass
class MarkResult:
    path: Path
    changed: bool
    had_frontmatter: bool


def ensure_synthetic_frontmatter(text: str) -> tuple[str, bool, bool]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        normalized = text.lstrip("\ufeff")
        updated = f"---\nsynthetic: true\n---\n{normalized}"
        return updated, True, False

    start, meta_text, closing, body = match.groups()
    lines = meta_text.splitlines()
    for idx, line in enumerate(lines):
        if re.match(r"^\s*synthetic\s*:", line):
            if re.match(r"^\s*synthetic\s*:\s*true\s*$", line):
                return text, False, True
            indent = re.match(r"^(\s*)", line).group(1)
            lines[idx] = f"{indent}synthetic: true"
            new_meta = "\n".join(lines)
            return f"{start}{new_meta}{closing}{body}", True, True

    new_meta = meta_text.rstrip("\n")
    if new_meta:
        new_meta = f"{new_meta}\nsynthetic: true"
    else:
        new_meta = "synthetic: true"
    return f"{start}{new_meta}{closing}{body}", True, True


def mark_file(path: Path) -> MarkResult:
    original = path.read_text(encoding="utf-8")
    updated, changed, had_frontmatter = ensure_synthetic_frontmatter(original)
    if changed:
        path.write_text(updated, encoding="utf-8")
    return MarkResult(path=path, changed=changed, had_frontmatter=had_frontmatter)


def iter_markdown_files(examples_dir: Path) -> list[Path]:
    return sorted(path for path in examples_dir.glob("*.md") if path.is_file())


def run(examples_dir: Path) -> tuple[int, int]:
    changed = 0
    total = 0
    for path in iter_markdown_files(examples_dir):
        result = mark_file(path)
        total += 1
        changed += int(result.changed)
    return changed, total


def main() -> int:
    parser = argparse.ArgumentParser(description="Add synthetic: true to example markdown frontmatter.")
    parser.add_argument("--examples-dir", type=Path, default=DEFAULT_EXAMPLES_DIR)
    args = parser.parse_args()

    changed, total = run(args.examples_dir)
    print(f"[OK] scanned={total} changed={changed} dir={args.examples_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
