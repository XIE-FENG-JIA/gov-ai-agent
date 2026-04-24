#!/usr/bin/env python3
"""Audit script: detect Type 1 module-local-binding candidates.

Type 1 iceberg: a test patches ``src.A.foo`` but ``src.B`` imported ``foo``
via ``from src.A import foo`` at load time, creating a local binding that the
patch never reaches.

This script scans the *test suite* for ``patch("src.X.Y.Z")`` calls and
cross-references the production code to find modules that do
``from src.X.Y import Z``, signalling that ``Z`` is locally bound and the
patch will miss unless it targets the *consuming* module.

Usage::

    python scripts/audit_local_binding.py --dry-run
    python scripts/audit_local_binding.py --module src/api/routes/workflow/_endpoints.py
    python scripts/audit_local_binding.py --json

Exit codes:
    0  No candidates found (or --dry-run reporting only)
    1  Candidates found (informational; not a hard failure in CI)
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent


class LocalBindCandidate(NamedTuple):
    """A potential Type 1 iceberg site."""

    test_file: str         # file containing the patch() call
    test_line: int         # line number of the patch() call
    patch_target: str      # string passed to patch(), e.g. "src.A.foo"
    src_module: str        # source module that defines the symbol, e.g. "src.A"
    symbol: str            # symbol name, e.g. "foo"
    consuming_modules: list[str]  # modules that import symbol from src_module


# ---------------------------------------------------------------------------
# Step 1: collect patch targets from test files
# ---------------------------------------------------------------------------

_PATCH_RE = re.compile(r'''patch\(\s*["']([^"']+)["']''')


def collect_patch_targets(test_root: Path) -> list[tuple[str, int, str]]:
    """Return (file, line, patch_target) for all patch() calls in tests."""
    results: list[tuple[str, int, str]] = []
    base = test_root.parent
    for f in test_root.rglob("*.py"):
        if "integration" in f.parts:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        try:
            rel = str(f.relative_to(base))
        except ValueError:
            rel = str(f)
        for lineno, line in enumerate(text.splitlines(), start=1):
            for m in _PATCH_RE.finditer(line):
                target = m.group(1)
                if target.startswith("src."):
                    results.append((rel, lineno, target))
    return results


# ---------------------------------------------------------------------------
# Step 2: build a map of  src_module → {symbol → [consuming_src_modules]}
# ---------------------------------------------------------------------------

def _parse_imports(src_root: Path) -> dict[str, dict[str, list[str]]]:
    """Parse all 'from src.X import Y' in src/ and build an index.

    Returns:
        { src_module: { symbol: [consuming_module, ...] } }
    """
    index: dict[str, dict[str, list[str]]] = {}
    base = src_root.parent
    for f in src_root.rglob("*.py"):
        try:
            rel_parts = f.relative_to(base).with_suffix("").parts
        except ValueError:
            rel_parts = f.with_suffix("").parts
        module_path = ".".join(rel_parts)
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if not node.module or not node.module.startswith("src."):
                continue
            for alias in node.names:
                sym = alias.name
                src_mod = node.module
                index.setdefault(src_mod, {}).setdefault(sym, []).append(module_path)
    return index


# ---------------------------------------------------------------------------
# Step 3: correlate patch targets with local-binding index
# ---------------------------------------------------------------------------

def find_candidates(
    patch_targets: list[tuple[str, int, str]],
    binding_index: dict[str, dict[str, list[str]]],
) -> list[LocalBindCandidate]:
    """Cross-reference patch targets with the local-binding index.

    A candidate is a patch call ``patch("src.A.B.symbol")`` where
    ``src.A.B`` has at least one consuming module that imported ``symbol``
    locally AND the consuming module is *different* from the patched path.
    """
    candidates: list[LocalBindCandidate] = []
    for test_file, test_line, target in patch_targets:
        parts = target.rsplit(".", 1)
        if len(parts) != 2:
            continue
        src_mod, symbol = parts
        if src_mod not in binding_index:
            continue
        sym_consumers = binding_index[src_mod].get(symbol, [])
        if not sym_consumers:
            continue
        # Consumers that are *different* from the patched module are risky
        risky = [c for c in sym_consumers if c != src_mod]
        if risky:
            candidates.append(
                LocalBindCandidate(
                    test_file=test_file,
                    test_line=test_line,
                    patch_target=target,
                    src_module=src_mod,
                    symbol=symbol,
                    consuming_modules=risky,
                )
            )
    return candidates


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _format_human(candidates: list[LocalBindCandidate]) -> str:
    if not candidates:
        return "audit_local_binding: no Type 1 candidates found ✓"
    lines = [
        f"audit_local_binding: {len(candidates)} Type 1 candidate(s) found",
        "",
    ]
    for c in candidates:
        lines.append(f"  {c.test_file}:{c.test_line}")
        lines.append(f"    patch target : {c.patch_target}")
        lines.append(f"    symbol bound : {c.src_module}.{c.symbol}")
        lines.append(f"    in consumers : {', '.join(c.consuming_modules)}")
        lines.append(
            f"    suggestion   : patch(\"{c.consuming_modules[0]}.{c.symbol}\", ...)"
        )
        lines.append("")
    return "\n".join(lines)


def _format_json(candidates: list[LocalBindCandidate]) -> str:
    return json.dumps([c._asdict() for c in candidates], indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Audit Type 1 local-binding iceberg candidates."
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Report candidates and exit 0 regardless of count.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output JSON instead of human-readable text.",
    )
    p.add_argument(
        "--module",
        metavar="PATH",
        help="Only check patches whose target starts with the dotted form of PATH.",
    )
    p.add_argument(
        "--src-root",
        default=str(ROOT / "src"),
        metavar="DIR",
        help="Root of the source tree (default: %(default)s).",
    )
    p.add_argument(
        "--test-root",
        default=str(ROOT / "tests"),
        metavar="DIR",
        help="Root of the test tree (default: %(default)s).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    src_root = Path(args.src_root)
    test_root = Path(args.test_root)

    patch_targets = collect_patch_targets(test_root)

    if args.module:
        # Convert file path to dotted module and filter
        mod_filter = (
            args.module.replace("/", ".").replace("\\", ".").removesuffix(".py")
        )
        patch_targets = [
            (f, l, t) for f, l, t in patch_targets if t.startswith(mod_filter)
        ]

    binding_index = _parse_imports(src_root)
    candidates = find_candidates(patch_targets, binding_index)

    if args.output_json:
        print(_format_json(candidates))
    else:
        print(_format_human(candidates))

    if args.dry_run:
        return 0
    return 1 if candidates else 0


if __name__ == "__main__":
    sys.exit(main())
