#!/usr/bin/env python3
"""Probe each live source adapter for latency and record count.

Runs a quick dry-fetch (limit=3) for each adapter and writes a JSON report to
``scripts/adapter_health_report.json``.  Integrates with ``sensor_refresh.py``
via :func:`check_adapter_health` to surface adapter stalls as soft violations.

Usage::

    python scripts/adapter_health.py --dry-run        # mock-zero report; no live calls
    python scripts/adapter_health.py                  # live fetch (requires network)
    python scripts/adapter_health.py --human          # icon + adapter + latency + count
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REPORT_PATH = Path(__file__).resolve().parent / "adapter_health_report.json"

# Registry of adapter names → import path and class name.
# Each entry: (module_dotted_path, class_name)
_ADAPTER_REGISTRY: list[tuple[str, str, str]] = [
    ("mojlaw", "src.sources.mojlaw", "MojLawAdapter"),
    ("executive_yuan_rss", "src.sources.executive_yuan_rss", "ExecutiveYuanRssAdapter"),
    ("mohw_rss", "src.sources.mohw_rss", "MohwRssAdapter"),
    ("fda_api", "src.sources.fda_api", "FdaApiAdapter"),
    ("datagovtw", "src.sources.datagovtw", "DataGovTwAdapter"),
]


def _probe_adapter(name: str, module_path: str, class_name: str, limit: int = 3) -> dict[str, Any]:
    """Probe a single adapter: import, instantiate, list(limit=3).

    Returns a result dict with keys: adapter, status, latency_ms, count, error.
    """
    import importlib
    start = time.monotonic()
    try:
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        adapter = cls()
        records = list(adapter.list(limit=limit))
        latency_ms = round((time.monotonic() - start) * 1000)
        count = len(records)
        status = "ok" if count > 0 else "zero_records"
        return {
            "adapter": name,
            "status": status,
            "latency_ms": latency_ms,
            "count": count,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001  intentional catch-all for probe safety
        latency_ms = round((time.monotonic() - start) * 1000)
        return {
            "adapter": name,
            "status": "error",
            "latency_ms": latency_ms,
            "count": 0,
            "error": str(exc),
        }


def _dry_run_report() -> list[dict[str, Any]]:
    """Return a mock-zero report (no live calls) for --dry-run mode.

    Status is ``dry_run_only`` (≠ ``ok``) so sensor can detect all-dry-run runs
    as a soft violation (T-ADAPTER-HEALTH-DRY-RUN-PATCH).
    """
    return [
        {
            "adapter": name,
            "status": "dry_run_only",
            "latency_ms": 0,
            "count": 0,
            "error": None,
        }
        for name, _, _ in _ADAPTER_REGISTRY
    ]


class AdapterHealthProbe:
    """Probe all registered source adapters and produce a health report."""

    def __init__(self, report_path: Path = _REPORT_PATH) -> None:
        self.report_path = report_path

    def run(self, dry_run: bool = False, limit: int = 3) -> dict[str, Any]:
        """Run probes and return the full report dict.

        Args:
            dry_run: If True, skip live fetch and write a mock-zero report.
            limit: Max records to fetch per adapter (live mode only).

        Returns:
            Report dict with keys ``adapters`` (list) and ``measured_at``.
        """
        if dry_run:
            results = _dry_run_report()
        else:
            results = [
                _probe_adapter(name, mod, cls, limit=limit)
                for name, mod, cls in _ADAPTER_REGISTRY
            ]

        report: dict[str, Any] = {
            "adapters": results,
            "measured_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run,
        }
        self._save(report)
        return report

    def _save(self, report: dict[str, Any]) -> None:
        try:
            self.report_path.parent.mkdir(parents=True, exist_ok=True)
            self.report_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            print(f"[adapter_health] WARNING: could not write report: {exc}", file=sys.stderr)


def format_human(report: dict[str, Any]) -> str:
    """Format a human-readable summary of the adapter health report."""
    lines = ["# Adapter Health Report"]
    if report.get("dry_run"):
        lines.append("*(dry-run mode -- no live fetches)*")
    lines.append(f"measured_at: {report.get('measured_at', 'unknown')}")
    lines.append("")
    for entry in report.get("adapters", []):
        status = entry.get("status", "unknown")
        if status == "ok":
            icon = "[OK]"
        elif status in ("zero_records", "dry_run_only"):
            icon = "[!] "
        else:
            icon = "[X] "
        latency = entry.get("latency_ms", 0)
        count = entry.get("count", 0)
        name = entry.get("adapter", "?")
        err = entry.get("error") or ""
        suffix = f" -- {err}" if err else ""
        lines.append(f"{icon} {name:25s}  latency={latency:5d}ms  count={count}{suffix}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="skip live fetch; write mock-zero report")
    parser.add_argument("--human", action="store_true", help="print human-readable summary to stdout")
    parser.add_argument("--limit", type=int, default=3, help="max records per adapter (default 3)")
    parser.add_argument(
        "--report",
        type=Path,
        default=_REPORT_PATH,
        help="path to write JSON report (default: scripts/adapter_health_report.json)",
    )
    args = parser.parse_args(argv)

    # Ensure repo root is in sys.path so src.* imports resolve when run as script
    repo_str = str(_REPO_ROOT)
    if repo_str not in sys.path:
        sys.path.insert(0, repo_str)

    probe = AdapterHealthProbe(report_path=args.report)
    report = probe.run(dry_run=args.dry_run, limit=args.limit)

    if args.human:
        print(format_human(report))
    else:
        print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
