#!/usr/bin/env python3
"""Measure pytest suite runtime and persist to scripts/pytest_runtime_baseline.json.

Records elapsed wall-clock time for a full test run (excluding integration tests)
and implements ratchet-down semantics for the ceiling:

- First run: ceiling_s = last_s × 1.5
- Subsequent runs: if last_s < ceiling_s, update ceiling_s = last_s × 1.5
  (ceiling improves, never worsens)
- If last_s > ceiling_s: ceiling stays, sensor will fire a soft violation

Usage::

    python scripts/measure_pytest_runtime.py --dry-run      # skip pytest; last_s=0.0
    python scripts/measure_pytest_runtime.py                # run full suite
    python scripts/measure_pytest_runtime.py --timeout 300  # custom timeout (seconds)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASELINE_PATH = Path(__file__).resolve().parent / "pytest_runtime_baseline.json"
_DEFAULT_TIMEOUT = 600
_DEFAULT_TOLERANCE = 0.20


def _load_baseline(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_baseline(path: Path, data: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"[measure_pytest_runtime] WARNING: could not write baseline: {exc}", file=sys.stderr)


def run_pytest(repo: Path, timeout: int) -> float:
    """Run pytest and return wall-clock seconds.  Returns 0.0 on failure."""
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/", "--ignore=tests/integration",
        "-q", "--tb=no", "--no-header",
    ]
    start = time.monotonic()
    try:
        subprocess.run(
            cmd,
            cwd=str(repo),
            check=False,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"[measure_pytest_runtime] pytest timed out after {timeout}s", file=sys.stderr)
        return float(timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"[measure_pytest_runtime] pytest failed: {exc}", file=sys.stderr)
        return 0.0
    return round(time.monotonic() - start, 2)


def update_baseline(path: Path, last_s: float, tolerance: float = _DEFAULT_TOLERANCE) -> dict:
    """Apply ratchet-down semantics and persist the baseline.

    Returns the final baseline dict (for testing/inspection).
    """
    data = _load_baseline(path)

    measured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    current_ceiling = float(data.get("ceiling_s", 0.0))

    if current_ceiling <= 0:
        # First run — initialise ceiling with headroom buffer.
        new_ceiling = last_s * 1.5 if last_s > 0 else 0.0
    elif last_s > 0 and last_s < current_ceiling:
        # Ratchet-down: new run is faster → lower the ceiling.
        new_ceiling = last_s * 1.5
    else:
        # No ratchet-up (run was slower or equal, or dry-run).
        new_ceiling = current_ceiling

    data.update({
        "ceiling_s": round(new_ceiling, 2),
        "last_s": last_s,
        "tolerance": tolerance,
        "measured_at": measured_at,
    })

    _save_baseline(path, data)
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip actual pytest execution; write last_s=0.0 to baseline",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=_DEFAULT_TIMEOUT,
        help=f"Max seconds to wait for pytest (default: {_DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--baseline-path",
        type=Path,
        default=_BASELINE_PATH,
        help="Path to output JSON baseline file",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=_REPO_ROOT,
        help="Repository root (default: auto-detected)",
    )
    args = parser.parse_args(argv)

    if args.dry_run:
        last_s = 0.0
        print("[measure_pytest_runtime] dry-run: skipping pytest, last_s=0.0")
    else:
        print(f"[measure_pytest_runtime] running pytest (timeout={args.timeout}s)…")
        last_s = run_pytest(args.repo, args.timeout)
        print(f"[measure_pytest_runtime] elapsed: {last_s:.2f}s")

    result = update_baseline(args.baseline_path, last_s)
    print(
        f"[measure_pytest_runtime] baseline updated: "
        f"ceiling_s={result['ceiling_s']}, last_s={result['last_s']}, "
        f"tolerance={result['tolerance']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
