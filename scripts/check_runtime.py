#!/usr/bin/env python3
"""Measure cold-start pytest runtime and ratchet against soft/hard limits.

Usage:
    python scripts/check_runtime.py [--strict] [--no-measure] [--repo PATH]

Exit codes:
    0  clean (or below soft limit)
    1  soft violation (>200s) when --strict
    2  hard violation (>300s)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASELINE_PATH = Path(__file__).resolve().parent / "runtime_baseline.json"

SOFT_LIMIT = 200.0
HARD_LIMIT = 300.0
DEFAULT_TOLERANCE = 0.20


def measure_cold_runtime(repo: Path) -> float:
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/", "--ignore=tests/integration",
        "-q", "--tb=no", "--no-header", "-n", "8",
    ]
    start = time.monotonic()
    try:
        subprocess.run(cmd, cwd=str(repo), check=False, capture_output=True)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"[check_runtime] pytest failed: {exc}", file=sys.stderr)
        return 0.0
    return time.monotonic() - start


def load_baseline(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_baseline(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def baseline_runtime_secs(baseline: dict) -> float:
    try:
        last = float(baseline.get("last_measured_secs", 0.0))
        if last > 0:
            return last
        return float(baseline.get("pytest_cold_runtime_secs", 0.0))
    except (TypeError, ValueError):
        return 0.0


def ceiling_violation(secs: float, baseline: dict) -> str | None:
    try:
        ceiling = float(baseline.get("ceiling_secs", 0.0))
        tolerance = float(baseline.get("tolerance_pct", DEFAULT_TOLERANCE))
    except (TypeError, ValueError):
        return None
    threshold = ceiling * (1 + tolerance)
    if ceiling > 0 and secs > threshold:
        return f"{secs:.1f}s > ceiling {ceiling:.1f}s * (1+{tolerance:.0%}) = {threshold:.1f}s"
    return None


def update_baseline_runtime(baseline: dict, secs: float) -> dict:
    baseline["last_measured_secs"] = round(secs, 2)
    current = float(baseline.get("pytest_cold_runtime_secs", 0.0) or 0.0)
    if current <= 0 or secs <= current:
        baseline["pytest_cold_runtime_secs"] = round(secs, 2)
    baseline.setdefault("ceiling_secs", 100.0)
    baseline.setdefault("tolerance_pct", DEFAULT_TOLERANCE)
    return baseline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--strict", action="store_true", help="exit 1 if soft limit (200s) breached")
    parser.add_argument("--no-measure", action="store_true", help="skip pytest run; check stored baseline only")
    parser.add_argument("--repo", type=Path, default=_REPO_ROOT)
    args = parser.parse_args(argv)

    baseline = load_baseline(_BASELINE_PATH)

    if args.no_measure:
        secs = baseline_runtime_secs(baseline)
        print(f"[check_runtime] stored runtime: {secs:.1f}s (--no-measure)")
    else:
        print("[check_runtime] measuring cold-start pytest runtime …")
        secs = measure_cold_runtime(args.repo)
        print(f"[check_runtime] measured: {secs:.1f}s")
        if secs > 0:
            save_baseline(_BASELINE_PATH, update_baseline_runtime(baseline, secs))

    if secs > HARD_LIMIT:
        print(f"[check_runtime] HARD violation: {secs:.1f}s > {HARD_LIMIT}s", file=sys.stderr)
        return 2

    if args.strict and secs > SOFT_LIMIT:
        print(f"[check_runtime] SOFT violation: {secs:.1f}s > {SOFT_LIMIT}s", file=sys.stderr)
        return 1

    ceiling_message = ceiling_violation(secs, baseline)
    if args.strict and ceiling_message:
        print(f"[check_runtime] SOFT violation: {ceiling_message} (up-creep)", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
