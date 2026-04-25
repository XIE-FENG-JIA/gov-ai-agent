"""Minimal ingest pipeline for public government source adapters."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from src.core.models import PublicGovDoc
from src.sources.base import BaseSourceAdapter
from src.sources.datagovtw import DataGovTwAdapter
from src.sources.executive_yuan_rss import ExecutiveYuanRssAdapter
from src.sources.fda_api import FdaApiAdapter
from src.sources.mohw_rss import MohwRssAdapter
from src.sources.mojlaw import MojLawAdapter
from src.sources.pcc import PccAdapter


DEFAULT_BASE_DIR = Path("kb_data")


class FixtureFallbackError(RuntimeError):
    """Raised when a caller requires live upstream data but only fixtures are available."""


@dataclass
class IngestRecord:
    """Paths produced for one normalized public document."""

    source_id: str
    raw_path: Path
    corpus_path: Path


@dataclass
class SourceSnapshot:
    """Current on-disk ingest state for one source."""

    source_key: str
    storage_name: str
    raw_count: int
    raw_bytes: int
    corpus_count: int
    latest_corpus_path: Path | None
    latest_corpus_mtime: float | None
    last_crawl_mtime: float | None


def ingest(
    adapter: BaseSourceAdapter,
    since_date: date | None = None,
    limit: int = 3,
    *,
    base_dir: Path = DEFAULT_BASE_DIR,
    require_live: bool = False,
) -> list[IngestRecord]:
    """Fetch, normalize, and persist source documents to kb_data."""
    adapter_name = _adapter_name(adapter)
    raw_root = base_dir / "raw" / adapter_name
    corpus_root = base_dir / "corpus" / adapter_name
    corpus_root.mkdir(parents=True, exist_ok=True)

    records: list[IngestRecord] = []
    for item in _list_documents(adapter, since_date=since_date, limit=limit):
        source_id = str(item.get("id", "")).strip()
        if not source_id:
            continue

        safe_id = _safe_filename(source_id)
        corpus_path = corpus_root / f"{safe_id}.md"
        existing_metadata = _read_corpus_metadata(corpus_path) if corpus_path.exists() else None
        if existing_metadata and not _should_upgrade_existing(existing_metadata):
            continue

        raw = adapter.fetch(source_id)
        normalized = adapter.normalize(raw)
        if existing_metadata and normalized.synthetic:
            continue
        if require_live and (normalized.synthetic or normalized.fixture_fallback):
            raise FixtureFallbackError(
                f"live ingest required for {adapter_name}, but source_id={source_id} used fixture fallback"
            )

        month_bucket = normalized.crawl_date.strftime("%Y%m")
        raw_path = raw_root / month_bucket / f"{safe_id}.json"
        _write_raw_snapshot(raw_path, raw)

        persisted_doc = normalized.model_copy(update={"raw_snapshot_path": str(raw_path)})
        _write_corpus_markdown(corpus_path, persisted_doc)
        records.append(IngestRecord(source_id=source_id, raw_path=raw_path, corpus_path=corpus_path))

    return records


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest public government docs into kb_data.")
    parser.add_argument("--source", choices=sorted(_adapter_registry()), required=True)
    parser.add_argument("--since", help="ISO date filter, e.g. 2026-01-01")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR))
    parser.add_argument("--require-live", action="store_true", help="fail if ingest falls back to local fixtures")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    adapter_cls = _adapter_registry()[args.source]
    try:
        records = ingest(
            adapter_cls(),
            since_date=date.fromisoformat(args.since) if args.since else None,
            limit=args.limit,
            base_dir=Path(args.base_dir),
            require_live=args.require_live,
        )
    except FixtureFallbackError as exc:
        print(f"error={exc}")
        return 2

    print(f"ingested={len(records)} source={args.source}")
    for record in records:
        print(record.corpus_path.as_posix())
    return 0


def _adapter_registry() -> dict[str, type[BaseSourceAdapter]]:
    return {
        "datagovtw": DataGovTwAdapter,
        "executive_yuan_rss": ExecutiveYuanRssAdapter,
        "executiveyuanrss": ExecutiveYuanRssAdapter,
        "fda": FdaApiAdapter,
        "mohw": MohwRssAdapter,
        "mojlaw": MojLawAdapter,
        "pcc": PccAdapter,
    }


def collect_source_snapshots(*, base_dir: Path = DEFAULT_BASE_DIR) -> list[SourceSnapshot]:
    """Scan kb_data for per-source raw/corpus counts and latest corpus file."""
    snapshots: list[SourceSnapshot] = []
    for source_key, adapter_cls in sorted(_adapter_registry().items()):
        storage_name = _adapter_name(adapter_cls())
        raw_root = base_dir / "raw" / storage_name
        corpus_root = base_dir / "corpus" / storage_name
        raw_files = sorted(raw_root.rglob("*.json")) if raw_root.exists() else []
        corpus_files = sorted(corpus_root.rglob("*.md")) if corpus_root.exists() else []
        latest_corpus_path = max(corpus_files, key=lambda path: path.stat().st_mtime, default=None)
        latest_corpus_mtime = latest_corpus_path.stat().st_mtime if latest_corpus_path else None
        last_crawl_mtime = max((path.stat().st_mtime for path in raw_files), default=None)
        snapshots.append(
            SourceSnapshot(
                source_key=source_key,
                storage_name=storage_name,
                raw_count=len(raw_files),
                raw_bytes=sum(path.stat().st_size for path in raw_files),
                corpus_count=len(corpus_files),
                latest_corpus_path=latest_corpus_path,
                latest_corpus_mtime=latest_corpus_mtime,
                last_crawl_mtime=last_crawl_mtime,
            )
        )
    return snapshots


def _adapter_name(adapter: BaseSourceAdapter) -> str:
    name = adapter.__class__.__name__
    return name.removesuffix("Adapter").lower()


def _list_documents(adapter: BaseSourceAdapter, *, since_date: date | None, limit: int) -> list[dict[str, Any]]:
    docs = list(adapter.list(since_date=since_date, limit=limit))
    return docs[:limit]


def _write_raw_snapshot(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _write_corpus_markdown(path: Path, doc: PublicGovDoc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "title": _extract_title(doc.content_md, fallback=doc.source_doc_no or doc.source_id),
        "source_id": doc.source_id,
        "source_url": doc.source_url,
        "source_agency": doc.source_agency,
        "source_doc_no": doc.source_doc_no,
        "source_date": doc.source_date.isoformat() if doc.source_date else None,
        "doc_type": doc.doc_type,
        "raw_snapshot_path": doc.raw_snapshot_path,
        "crawl_date": doc.crawl_date.isoformat(),
        "synthetic": doc.synthetic,
        "fixture_fallback": doc.fixture_fallback,
    }
    frontmatter = yaml.dump(metadata, allow_unicode=True, default_flow_style=False, sort_keys=False).strip()
    path.write_text(f"---\n{frontmatter}\n---\n{doc.content_md}\n", encoding="utf-8")


def _extract_title(content_md: str, *, fallback: str) -> str:
    for line in content_md.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or fallback
    return fallback


def _read_corpus_metadata(path: Path) -> dict[str, Any] | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return None
    metadata = yaml.safe_load(parts[1])
    return metadata if isinstance(metadata, dict) else None


def _should_upgrade_existing(metadata: dict[str, Any]) -> bool:
    return bool(metadata.get("synthetic") or metadata.get("fixture_fallback"))


def _safe_filename(source_id: str) -> str:
    """Return a safe single-component filename from a source_id that may be a URL.

    Replaces URL scheme separators and characters that are invalid in Windows
    filenames so the resulting string can be used as a path stem.
    """
    safe = source_id.replace("://", "--")
    for ch in r'/\:*?"<>|':
        safe = safe.replace(ch, "_")
    return safe[:200]


if __name__ == "__main__":
    raise SystemExit(main())
