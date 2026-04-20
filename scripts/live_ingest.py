"""Run require-live ingest across source adapters and write a markdown report."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.purge_fixture_corpus import archive_fixture_corpus


DEFAULT_REPORT_PATH = Path("docs") / "live-ingest-report.md"
DEFAULT_BASE_DIR = Path("kb_data")
DEFAULT_SOURCES = ["mojlaw", "datagovtw", "executive_yuan_rss", "mohw", "fda"]
SOURCE_ALIASES = {
    "executiveyuanrss": "executive_yuan_rss",
    "executive_yuan_rss": "executive_yuan_rss",
}


@dataclass
class SourceRunResult:
    source: str
    status: str
    count: int
    summary: str
    records: list[dict[str, Any]]
    ingested_count: int = 0
    fixture_remaining: int = 0
    archived_count: int = 0


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run require-live ingest for one or more public sources.")
    parser.add_argument(
        "--sources",
        default=",".join(DEFAULT_SOURCES),
        help="Comma-separated source keys, e.g. mojlaw,datagovtw,executive_yuan_rss",
    )
    parser.add_argument("--limit", type=int, default=3, help="Max documents per source")
    parser.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR), help="Output kb_data root")
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH), help="Markdown report output path")
    parser.add_argument(
        "--require-live",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fail when adapters fall back to local fixtures (default: true).",
    )
    parser.add_argument(
        "--prune-fixture-fallback",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Archive existing fixture-backed corpus/raw files for sources that now have live docs.",
    )
    parser.add_argument("--archive-label", default=None, help="Optional archive folder label under kb_data/archive/")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    source_keys = _parse_sources(args.sources, parser)
    base_dir = Path(args.base_dir)
    report_path = Path(args.report_path)
    run_kwargs: dict[str, Any] = {
        "source_keys": source_keys,
        "limit": args.limit,
        "base_dir": base_dir,
        "require_live": args.require_live,
    }
    if args.prune_fixture_fallback or args.archive_label is not None:
        run_kwargs["prune_fixture_fallback"] = args.prune_fixture_fallback
        run_kwargs["archive_label"] = args.archive_label
    results = run_live_ingest(**run_kwargs)
    write_report(report_path, results=results, base_dir=base_dir, limit=args.limit, force_live=args.require_live)
    return 0 if all(result.status == "PASS" for result in results) else 1


def run_live_ingest(
    *,
    source_keys: list[str],
    limit: int,
    base_dir: Path,
    require_live: bool = True,
    prune_fixture_fallback: bool = False,
    archive_label: str | None = None,
) -> list[SourceRunResult]:
    registry = _available_sources()
    ingest_fn = _load_ingest_function()
    results: list[SourceRunResult] = []
    previous_force_live = os.environ.get("GOV_AI_FORCE_LIVE")
    if require_live:
        os.environ["GOV_AI_FORCE_LIVE"] = "1"
    try:
        for source_key in source_keys:
            adapter_cls = registry[source_key]
            adapter = adapter_cls()
            storage_names = _storage_names(source_key=source_key, adapter=adapter)
            try:
                records = ingest_fn(adapter, limit=limit, base_dir=base_dir, require_live=require_live)
                archived_count = 0
                if prune_fixture_fallback:
                    archived_count = len(
                        archive_fixture_corpus(
                            base_dir=base_dir,
                            storage_names=storage_names,
                            archive_label=archive_label,
                        )
                    )
                rows = _read_source_records(base_dir=base_dir, storage_names=storage_names)
                live_rows = [row for row in rows if not row["fixture_fallback"] and not row["archived_fixture"]]
                fixture_remaining = sum(1 for row in rows if row["fixture_fallback"])
                results.append(
                    SourceRunResult(
                        source=source_key,
                        status="PASS",
                        count=len(live_rows),
                        summary=(
                            f"ingested={len(records)} live_total={len(live_rows)} "
                            f"fixture_remaining={fixture_remaining} archived={archived_count}"
                        ),
                        records=live_rows,
                        ingested_count=len(records),
                        fixture_remaining=fixture_remaining,
                        archived_count=archived_count,
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


def write_report(
    report_path: Path,
    *,
    results: list[SourceRunResult],
    base_dir: Path,
    limit: int,
    force_live: bool,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Live Ingest Report",
        "",
        f"- base_dir: {base_dir.as_posix()}",
        f"- limit: {limit}",
        f"- force_live: {int(force_live)}",
        "",
    ]
    for result in results:
        lines.extend(
            [
                f"## {result.source}",
                f"- status: {result.status}",
                f"- count: {result.count}",
                f"- live_count: {len(result.records)}",
                f"- ingested_count: {result.ingested_count}",
                f"- fixture_remaining: {result.fixture_remaining}",
                f"- archived_count: {result.archived_count}",
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
    available = _available_sources()
    source_keys = [_normalize_source_key(item) for item in raw_sources.split(",") if item.strip()]
    if not source_keys:
        parser.error("--sources must include at least one source key")
    invalid = [key for key in source_keys if key not in available]
    if invalid:
        parser.error(f"unsupported source(s): {', '.join(invalid)}")
    return source_keys


def _normalize_source_key(raw_source: str) -> str:
    normalized = raw_source.strip().lower().replace("-", "_")
    return SOURCE_ALIASES.get(normalized, normalized)


@lru_cache(maxsize=1)
def _available_sources() -> dict[str, type[Any]]:
    registry = _load_registry()
    available = dict(registry)
    for alias, canonical in SOURCE_ALIASES.items():
        if canonical in registry:
            available[canonical] = registry[canonical]
    return available


@lru_cache(maxsize=1)
def _load_registry() -> dict[str, type[Any]]:
    from src.sources.ingest import _adapter_registry

    registry = dict(_adapter_registry())
    if "executiveyuanrss" in registry:
        registry["executive_yuan_rss"] = registry["executiveyuanrss"]
    return registry


@lru_cache(maxsize=1)
def _load_ingest_function() -> Any:
    from src.sources.ingest import ingest

    return ingest


def _read_record(corpus_path: Path) -> dict[str, Any]:
    text = corpus_path.read_text(encoding="utf-8")
    _, raw_meta, body = text.split("---\n", 2)
    metadata = yaml.safe_load(raw_meta) or {}
    return {
        "path": corpus_path.as_posix(),
        "source_url": str(metadata.get("source_url", "")).replace("|", "%7C"),
        "synthetic": bool(metadata.get("synthetic")),
        "fixture_fallback": bool(metadata.get("fixture_fallback")),
        "deprecated": bool(metadata.get("deprecated")),
        "archived_fixture": bool(metadata.get("archived_fixture")),
        "first_sentence": _first_sentence(body),
    }


def _storage_names(*, source_key: str, adapter: Any) -> list[str]:
    candidates = [
        adapter.__class__.__name__.removesuffix("Adapter").lower(),
        source_key.lower().replace("_", ""),
        source_key.lower(),
    ]
    return list(dict.fromkeys(name for name in candidates if name))


def _read_source_records(*, base_dir: Path, storage_names: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()
    for storage_name in storage_names:
        corpus_root = base_dir / "corpus" / storage_name
        if not corpus_root.exists():
            continue
        for path in sorted(corpus_root.rglob("*.md")):
            if path in seen_paths:
                continue
            seen_paths.add(path)
            record = _read_record(path)
            if record["deprecated"] and record["archived_fixture"]:
                continue
            rows.append(record)
    return rows


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
