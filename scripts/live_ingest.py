"""Run require-live ingest across source adapters and write a markdown report."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.sources.ingest import DEFAULT_BASE_DIR, _adapter_registry, ingest


DEFAULT_REPORT_PATH = Path("docs") / "live-ingest-report.md"


@dataclass
class SourceRunResult:
    source: str
    status: str
    count: int
    summary: str
    records: list[dict[str, Any]]


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run require-live ingest for one or more public sources.")
    parser.add_argument(
        "--sources",
        default=",".join(sorted(_adapter_registry())),
        help="Comma-separated source keys, e.g. mojlaw,datagovtw,executiveyuanrss",
    )
    parser.add_argument("--limit", type=int, default=3, help="Max documents per source")
    parser.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR), help="Output kb_data root")
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH), help="Markdown report output path")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    source_keys = _parse_sources(args.sources, parser)
    base_dir = Path(args.base_dir)
    report_path = Path(args.report_path)
    results = run_live_ingest(source_keys=source_keys, limit=args.limit, base_dir=base_dir)
    write_report(report_path, results=results, base_dir=base_dir, limit=args.limit)
    return 0 if all(result.status == "PASS" for result in results) else 1


def run_live_ingest(*, source_keys: list[str], limit: int, base_dir: Path) -> list[SourceRunResult]:
    registry = _adapter_registry()
    results: list[SourceRunResult] = []
    previous_force_live = os.environ.get("GOV_AI_FORCE_LIVE")
    os.environ["GOV_AI_FORCE_LIVE"] = "1"
    try:
        for source_key in source_keys:
            adapter = registry[source_key]()
            try:
                records = ingest(adapter, limit=limit, base_dir=base_dir, require_live=True)
                rows = [_read_record(record.corpus_path) for record in records]
                results.append(
                    SourceRunResult(
                        source=source_key,
                        status="PASS",
                        count=len(rows),
                        summary=f"ingested={len(rows)}",
                        records=rows,
                    )
                )
            except Exception as exc:  # pragma: no cover - exercised in script tests via mocks
                results.append(
                    SourceRunResult(
                        source=source_key,
                        status="FAIL",
                        count=0,
                        summary=str(exc),
                        records=[],
                    )
                )
    finally:
        if previous_force_live is None:
            os.environ.pop("GOV_AI_FORCE_LIVE", None)
        else:
            os.environ["GOV_AI_FORCE_LIVE"] = previous_force_live
    return results


def write_report(report_path: Path, *, results: list[SourceRunResult], base_dir: Path, limit: int) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Live Ingest Report",
        "",
        f"- base_dir: {base_dir.as_posix()}",
        f"- limit: {limit}",
        f"- force_live: {os.environ.get('GOV_AI_FORCE_LIVE', '0')}",
        "",
    ]
    for result in results:
        lines.extend(
            [
                f"## {result.source}",
                f"- status: {result.status}",
                f"- count: {result.count}",
                f"- summary: {result.summary}",
            ]
        )
        if result.records:
            lines.append("")
            lines.append("| source_url | synthetic | fixture_fallback | first_sentence |")
            lines.append("| --- | --- | --- | --- |")
            for row in result.records:
                lines.append(
                    "| {source_url} | {synthetic} | {fixture_fallback} | {first_sentence} |".format(**row)
                )
        lines.append("")
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _parse_sources(raw_sources: str, parser: argparse.ArgumentParser) -> list[str]:
    available = _adapter_registry()
    source_keys = [item.strip().lower() for item in raw_sources.split(",") if item.strip()]
    if not source_keys:
        parser.error("--sources must include at least one source key")
    invalid = [key for key in source_keys if key not in available]
    if invalid:
        parser.error(f"unsupported source(s): {', '.join(invalid)}")
    return source_keys


def _read_record(corpus_path: Path) -> dict[str, Any]:
    text = corpus_path.read_text(encoding="utf-8")
    _, raw_meta, body = text.split("---\n", 2)
    metadata = yaml.safe_load(raw_meta) or {}
    return {
        "source_url": str(metadata.get("source_url", "")).replace("|", "%7C"),
        "synthetic": bool(metadata.get("synthetic")),
        "fixture_fallback": bool(metadata.get("fixture_fallback")),
        "first_sentence": _first_sentence(body),
    }


def _first_sentence(body: str) -> str:
    lines = [line.strip().lstrip("#").strip() for line in body.splitlines() if line.strip()]
    text = " ".join(lines)
    if not text:
        return "-"
    for marker in ("。", ".", "!", "?", "\n"):
        if marker in text:
            head = text.split(marker, 1)[0].strip()
            return head or text[:120]
    return text[:120]


if __name__ == "__main__":
    raise SystemExit(main())
