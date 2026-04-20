from pathlib import Path

import typer

from ._shared import app, console
from .corpus import _ingest_fetch_results


def _maybe_ingest(results: list, do_ingest: bool) -> None:
    if not (do_ingest and results):
        return
    from . import _init_kb

    kb = _init_kb()
    count = _ingest_fetch_results(results, kb)
    console.print(f"[green]已匯入 {count} 筆至知識庫[/green]")
    console.print(f"目前資料庫統計：{kb.get_stats()}")


@app.command("fetch-laws")
def fetch_laws(
    output_dir: str = typer.Option("./kb_data/regulations/laws", help="輸出目錄"),
    laws: str = typer.Option("", help="指定法規 PCode（逗號分隔），空白則使用預設清單"),
    do_ingest: bool = typer.Option(False, "--ingest", "-I", help="擷取後自動匯入知識庫"),
    bulk: bool = typer.Option(False, "--bulk", help="使用 bulk XML 下載模式（全量下載）"),
) -> None:
    """從全國法規資料庫擷取法規全文（Level A 來源）。"""
    from src.knowledge.fetchers.constants import DEFAULT_LAW_PCODES
    from src.knowledge.fetchers.law_fetcher import LawFetcher

    pcodes = DEFAULT_LAW_PCODES
    if laws.strip():
        codes = [code.strip() for code in laws.split(",") if code.strip()]
        pcodes = {code: DEFAULT_LAW_PCODES.get(code, code) for code in codes}

    fetcher = LawFetcher(output_dir=Path(output_dir), pcodes=pcodes)
    results = fetcher.fetch_bulk() if bulk else fetcher.fetch()
    console.print(
        f"[bold]正在從{fetcher.name()}{' bulk 下載全量法規' if bulk else f'擷取 {len(pcodes)} 部法規'}...[/bold]"
    )
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")
    _maybe_ingest(results, do_ingest)


@app.command("fetch-gazette")
def fetch_gazette(
    output_dir: str = typer.Option("./kb_data/examples/gazette", help="輸出目錄"),
    days: int = typer.Option(7, help="擷取最近 N 天的公報"),
    category: str = typer.Option("", help="篩選特定類別（如：法規命令）"),
    do_ingest: bool = typer.Option(False, "--ingest", "-I", help="擷取後自動匯入知識庫"),
    bulk: bool = typer.Option(False, "--bulk", help="使用 bulk ZIP 下載模式（含 PDF）"),
    no_pdf: bool = typer.Option(False, "--no-pdf", help="bulk 模式下跳過 PDF 全文提取"),
) -> None:
    """從行政院公報擷取近期公報（Level A 來源）。"""
    from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

    fetcher = GazetteFetcher(
        output_dir=Path(output_dir),
        days=days,
        category_filter=category if category.strip() else None,
    )
    console.print(
        f"[bold]正在從{fetcher.name()}{' bulk 下載公報 ZIP' if bulk else f'擷取最近 {days} 天的公報'}...[/bold]"
    )
    results = fetcher.fetch_bulk(extract_pdf=not no_pdf) if bulk else fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")
    _maybe_ingest(results, do_ingest)


@app.command("fetch-opendata")
def fetch_opendata(
    output_dir: str = typer.Option("./kb_data/policies/opendata", help="輸出目錄"),
    keyword: str = typer.Option("警政署", help="搜尋關鍵字"),
    limit: int = typer.Option(10, help="最大資料集數量"),
    do_ingest: bool = typer.Option(False, "--ingest", "-I", help="擷取後自動匯入知識庫"),
) -> None:
    """從政府資料開放平臺搜尋資料集（Level B 來源）。"""
    from src.knowledge.fetchers.opendata_fetcher import OpenDataFetcher

    fetcher = OpenDataFetcher(output_dir=Path(output_dir), keyword=keyword, limit=limit)
    console.print(f"[bold]正在從{fetcher.name()}搜尋「{keyword}」...[/bold]")
    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")
    _maybe_ingest(results, do_ingest)


@app.command("fetch-npa")
def fetch_npa(
    output_dir: str = typer.Option("./kb_data/policies/npa", help="輸出目錄"),
    do_ingest: bool = typer.Option(False, "--ingest", "-I", help="擷取後自動匯入知識庫"),
) -> None:
    """從警政署 OPEN DATA 擷取警政資料集（Level B 來源）。"""
    from src.knowledge.fetchers.npa_fetcher import NpaFetcher

    fetcher = NpaFetcher(output_dir=Path(output_dir))
    console.print(f"[bold]正在從{fetcher.name()}擷取資料...[/bold]")
    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")
    _maybe_ingest(results, do_ingest)


@app.command("fetch-legislative")
def fetch_legislative(
    output_dir: str = typer.Option("./kb_data/policies/legislative", help="輸出目錄"),
    term: str = typer.Option("all", help="屆期（如 11），預設 all"),
    limit: int = typer.Option(50, help="最大議案數量"),
    do_ingest: bool = typer.Option(False, "--ingest", "-I", help="擷取後自動匯入知識庫"),
) -> None:
    """從立法院開放資料擷取議案（Level B 來源）。"""
    from src.knowledge.fetchers.legislative_fetcher import LegislativeFetcher

    fetcher = LegislativeFetcher(output_dir=Path(output_dir), term=term, limit=limit)
    console.print(f"[bold]正在從{fetcher.name()}擷取資料...[/bold]")
    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")
    _maybe_ingest(results, do_ingest)
