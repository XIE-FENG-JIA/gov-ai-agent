"""Nightly integration gate runner for live source smoke and ingest health."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = Path("docs") / "live-ingest-report.md"
DEFAULT_PYTEST_TARGET = Path("tests") / "integration" / "test_sources_smoke.py"
DEFAULT_SOURCES = ["mojlaw", "datagovtw", "executive_yuan_rss", "mohw", "fda"]


@dataclass(frozen=True)
class CommandSpec:
    label: str
    argv: tuple[str, ...]
    env_overrides: dict[str, str]


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run nightly integration checks for live public sources.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned commands without executing them.")
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable used to run pytest and scripts (default: current interpreter).",
    )
    parser.add_argument(
        "--pytest-target",
        default=str(DEFAULT_PYTEST_TARGET),
        help="Pytest target for live integration smoke.",
    )
    parser.add_argument(
        "--sources",
        default=",".join(DEFAULT_SOURCES),
        help="Comma-separated live source keys passed to scripts/live_ingest.py.",
    )
    parser.add_argument("--limit", type=int, default=1, help="Per-source live ingest limit (default: 1).")
    parser.add_argument(
        "--report-path",
        default=str(DEFAULT_REPORT_PATH),
        help="Markdown report path produced by scripts/live_ingest.py.",
    )
    parser.add_argument("--skip-pytest", action="store_true", help="Skip pytest live smoke step.")
    parser.add_argument("--skip-live-ingest", action="store_true", help="Skip live ingest health step.")
    return parser


def build_plan(
    *,
    python_executable: str,
    pytest_target: str,
    sources: str,
    limit: int,
    report_path: str,
    skip_pytest: bool,
    skip_live_ingest: bool,
) -> list[CommandSpec]:
    env_overrides = {"GOV_AI_RUN_INTEGRATION": "1"}
    plan: list[CommandSpec] = []

    if not skip_pytest:
        plan.append(
            CommandSpec(
                label="pytest live source smoke",
                argv=(
                    python_executable,
                    "-m",
                    "pytest",
                    pytest_target,
                    "-q",
                    "--no-header",
                ),
                env_overrides=env_overrides,
            )
        )

    if not skip_live_ingest:
        plan.append(
            CommandSpec(
                label="live ingest health report",
                argv=(
                    python_executable,
                    "scripts/live_ingest.py",
                    "--sources",
                    sources,
                    "--limit",
                    str(limit),
                    "--report-path",
                    report_path,
                    "--require-live",
                ),
                env_overrides=env_overrides,
            )
        )

    return plan


def render_command(spec: CommandSpec) -> str:
    env_prefix = " ".join(f"{key}={value}" for key, value in sorted(spec.env_overrides.items()))
    argv = " ".join(spec.argv)
    return f"{env_prefix} {argv}".strip()


def run_plan(plan: list[CommandSpec], *, dry_run: bool) -> int:
    if not plan:
        print("No nightly integration steps selected.")
        return 0

    for spec in plan:
        command_text = render_command(spec)
        print(f"[nightly] {spec.label}")
        print(f"  {command_text}")
        if dry_run:
            continue

        env = os.environ.copy()
        env.update(spec.env_overrides)
        completed = subprocess.run(spec.argv, cwd=ROOT_DIR, env=env, check=False)
        if completed.returncode != 0:
            print(f"[nightly] FAIL {spec.label} (exit={completed.returncode})")
            return completed.returncode

    print("[nightly] PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    plan = build_plan(
        python_executable=args.python,
        pytest_target=args.pytest_target,
        sources=args.sources,
        limit=args.limit,
        report_path=args.report_path,
        skip_pytest=args.skip_pytest,
        skip_live_ingest=args.skip_live_ingest,
    )
    return run_plan(plan, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
