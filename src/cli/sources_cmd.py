"""gov-ai sources — public source ingest commands."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import typer
from rich.console import Console

from src.sources.ingest import DEFAULT_BASE_DIR, IngestRecord, _adapter_registry, ingest as run_ingest


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


def _render_ingest_result(source_key: str, records: list[IngestRecord]) -> None:
    console.print(f"[green]完成[/green] 匯入 {len(records)} 筆，來源：{source_key}")
    for record in records:
        console.print(record.corpus_path.as_posix())
