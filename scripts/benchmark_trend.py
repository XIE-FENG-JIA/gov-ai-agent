#!/usr/bin/env python3
"""Benchmark trend tracker — appends a run entry to benchmark/trend.jsonl.

Reads a blind-eval result JSON file, extracts key metrics, appends a single
JSONL line to the trend file, and checks whether the new run regressed more
than ``REGRESSION_THRESHOLD`` (10 %) vs the previous entry.

Usage:
    python scripts/benchmark_trend.py benchmark/blind_eval_results.afterfix17.limit2.json

Exit codes:
    0  Appended successfully, no regression.
    1  Regression detected (avg_score dropped >10 % vs previous entry).
    2  Invalid input (missing file, bad JSON, missing summary).
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

TREND_FILE = Path("benchmark/trend.jsonl")
REGRESSION_THRESHOLD = 0.10


def load_eval_result(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if "summary" not in data:
        raise ValueError(f"No 'summary' key in {path}")
    return data


def make_trend_entry(data: dict, source_file: str) -> dict:
    summary = data["summary"]
    run_id = Path(source_file).stem
    return {
        "date": date.today().isoformat(),
        "run_id": run_id,
        "avg_score": summary.get("avg_score"),
        "total": summary.get("total"),
        "success_rate": summary.get("success_rate"),
        "goal_met_rate": summary.get("goal_met_rate"),
        "by_doc_type": {
            k: v.get("avg_score")
            for k, v in summary.get("by_doc_type", {}).items()
        },
        "source_file": source_file,
    }


def check_regression(trend_file: Path, new_entry: dict) -> tuple[bool, str]:
    """Return (is_regression, message). Compares against the last valid entry."""
    if not trend_file.exists():
        return False, ""
    lines = trend_file.read_text(encoding="utf-8").strip().splitlines()
    for line in reversed(lines):
        try:
            prev = json.loads(line)
            prev_score = prev.get("avg_score")
            new_score = new_entry.get("avg_score")
            if prev_score and new_score is not None and prev_score > 0:
                drop = (prev_score - new_score) / prev_score
                if drop > REGRESSION_THRESHOLD:
                    msg = (
                        f"REGRESSION: avg_score dropped {drop:.1%} "
                        f"({prev_score:.4f} -> {new_score:.4f}, "
                        f"threshold {REGRESSION_THRESHOLD:.0%})"
                    )
                    return True, msg
            return False, ""
        except (json.JSONDecodeError, KeyError):
            continue
    return False, ""


def append_entry(trend_file: Path, entry: dict) -> None:
    trend_file.parent.mkdir(parents=True, exist_ok=True)
    with open(trend_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Append a blind-eval run to benchmark/trend.jsonl"
    )
    parser.add_argument("result_file", help="Path to blind eval result JSON")
    parser.add_argument(
        "--trend-file",
        default=str(TREND_FILE),
        help=f"Trend file to append to (default: {TREND_FILE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the entry without writing to disk",
    )
    args = parser.parse_args(argv)

    result_path = Path(args.result_file)
    trend_path = Path(args.trend_file)

    if not result_path.exists():
        print(f"ERROR: {result_path} not found", file=sys.stderr)
        return 2

    try:
        data = load_eval_result(result_path)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    entry = make_trend_entry(data, str(result_path))
    is_regression, msg = check_regression(trend_path, entry)

    if args.dry_run:
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        if is_regression:
            print(f"\n{msg}", file=sys.stderr)
        return 1 if is_regression else 0

    append_entry(trend_path, entry)
    print(f"Appended to {trend_path}: avg_score={entry['avg_score']}, run_id={entry['run_id']}")

    if is_regression:
        print(f"\n{msg}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
