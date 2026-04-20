"""gov-ai sources — public source ingest commands."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from datetime import datetime

import typer
from rich.console import Console

from src.sources.ingest import (
    DEFAULT_BASE_DIR,
    IngestRecord,
    SourceSnapshot,
    _adapter_registry,
    collect_source_snapshots,
    ingest as run_ingest,
)


app = typer.Typer(help="公開政府資料來源匯入")
console = Console()


@app.command("ingest")
def ingest_command(
    source: str = typer.Option(..., "--source", "-s", help="來源代碼，例如 mojlaw / datagovtw / mohw"),
    since: str | None = typer.Option(None, "--since", help="ISO 日期過濾，例如 2026-01-01"),
    limit: int = typer.Option(3, "--limit", min=1, help="最多匯入幾筆文件"),
    base_dir: Path = typer.Option(DEFAULT_BASE_DIR, "--base-dir", help="匯出根目錄"),
) -> None:
    """Run the source adapter ingest pipeline from the main CLI."""
    registry = _adapter_registry()
    source_key = source.strip().lower()
    if source_key not in registry:
        raise typer.BadParameter(f"不支援的來源：{source}。可用來源：{', '.join(sorted(registry))}")

    try:
        since_date = date.fromisoformat(since) if since else None
    except ValueError as exc:
        raise typer.BadParameter("日期格式必須是 YYYY-MM-DD") from exc

    records = run_ingest(
        registry[source_key](),
        since_date=since_date,
        limit=limit,
        base_dir=base_dir,
    )
    _render_ingest_result(source_key, records)


@app.command("status")
def status_command(
    base_dir: Path = typer.Option(DEFAULT_BASE_DIR, "--base-dir", help="匯入根目錄"),
) -> None:
    """Show per-source ingest status from local kb_data."""
    snapshots = collect_source_snapshots(base_dir=base_dir)
    _render_status_result(snapshots)


@app.command("stats")
def stats_command(
    adapter: str | None = typer.Option(None, "--adapter", help="只看單一來源，例如 mojlaw"),
    base_dir: Path = typer.Option(DEFAULT_BASE_DIR, "--base-dir", help="匯入根目錄"),
) -> None:
    """Show aggregate ingest counts from local kb_data."""
    snapshots = collect_source_snapshots(base_dir=base_dir)
    _render_stats_result(snapshots, base_dir=base_dir, adapter=adapter)


def _render_ingest_result(source_key: str, records: list[IngestRecord]) -> None:
    console.print(f"[green]完成[/green] 匯入 {len(records)} 筆，來源：{source_key}")
    for record in records:
        console.print(record.corpus_path.as_posix())


def _render_status_result(snapshots: list[SourceSnapshot]) -> None:
    console.print("[bold cyan]公開來源狀態[/bold cyan]")
    for snapshot in snapshots:
        latest = "-"
        if snapshot.latest_corpus_path and snapshot.latest_corpus_mtime is not None:
            latest_ts = datetime.fromtimestamp(snapshot.latest_corpus_mtime).strftime("%Y-%m-%d %H:%M")
            latest = f"{snapshot.latest_corpus_path.name} @ {latest_ts}"
        last_crawl = "-"
        if snapshot.last_crawl_mtime is not None:
            last_crawl = datetime.fromtimestamp(snapshot.last_crawl_mtime).strftime("%Y-%m-%d %H:%M")
        console.print(
            f"{snapshot.source_key}: corpus={snapshot.corpus_count} raw={snapshot.raw_count} "
            f"raw_bytes={snapshot.raw_bytes} last_crawl={last_crawl} latest={latest}"
        )


def _render_stats_result(snapshots: list[SourceSnapshot], *, base_dir: Path, adapter: str | None) -> None:
    if adapter:
        source_key = adapter.strip().lower()
        snapshot = next((item for item in snapshots if item.source_key == source_key), None)
        if snapshot is None:
            raise typer.BadParameter(f"不支援的來源：{adapter}")
        console.print("[bold cyan]公開來源統計[/bold cyan]")
        console.print(f"base_dir={base_dir.as_posix()}")
        console.print(f"adapter={snapshot.source_key} storage={snapshot.storage_name}")
        console.print(f"corpus={snapshot.corpus_count} raw={snapshot.raw_count} raw_bytes={snapshot.raw_bytes}")
        return

    total_corpus = sum(snapshot.corpus_count for snapshot in snapshots)
    total_raw = sum(snapshot.raw_count for snapshot in snapshots)
    total_raw_bytes = sum(snapshot.raw_bytes for snapshot in snapshots)
    active_sources = sum(1 for snapshot in snapshots if snapshot.corpus_count or snapshot.raw_count)
    console.print("[bold cyan]公開來源統計[/bold cyan]")
    console.print(f"base_dir={base_dir.as_posix()}")
    console.print(f"sources={len(snapshots)} active={active_sources}")
    console.print(f"corpus={total_corpus} raw={total_raw} raw_bytes={total_raw_bytes}")
