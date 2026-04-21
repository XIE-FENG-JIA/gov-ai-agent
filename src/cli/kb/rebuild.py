from pathlib import Path

import typer

from src.knowledge.corpus_provenance import is_active_corpus_metadata

from ._shared import app, console
from .corpus import _ingest_fetch_results, _load_full_document, _sanitize_metadata, parse_markdown_with_metadata


_REBUILD_COLLECTIONS: tuple[tuple[str, str], ...] = (
    ("examples", "examples"),
    ("regulations", "regulations"),
    ("policies", "policies"),
)


def _maybe_ingest(results: list, do_ingest: bool) -> None:
    if not (do_ingest and results):
        return
    from . import _init_kb

    kb = _init_kb()
    count = _ingest_fetch_results(results, kb)
    console.print(f"[green]已匯入 {count} 筆至知識庫[/green]")
    console.print(f"目前資料庫統計：{kb.get_stats()}")


def _should_skip_rebuild_file(metadata: dict, only_real: bool) -> bool:
    if metadata.get("deprecated"):
        return True
    if not only_real:
        return False
    return not is_active_corpus_metadata(metadata)


@app.command("rebuild")
def rebuild(
    base_dir: str = typer.Option("./kb_data", "--base-dir", help="知識來源根目錄"),
    only_real: bool = typer.Option(
        False,
        "--only-real",
        help="只重建真實來源文件（跳過 synthetic / fixture_fallback）",
    ),
) -> None:
    """重建知識庫索引：重設 DB 後重新匯入 examples/regulations/policies。"""
    from . import _init_kb

    source_root = Path(base_dir)
    if not source_root.exists():
        console.print(f"[red]找不到知識來源根目錄：{base_dir}[/red]")
        raise typer.Exit(1)

    kb = _init_kb()
    console.print("[bold red]正在重建知識庫索引...[/bold red]")
    kb.reset_db()

    total_imported = 0
    total_skipped = 0
    total_missing_dirs = 0

    for collection, subdir_name in _REBUILD_COLLECTIONS:
        source_dir = source_root / subdir_name
        if not source_dir.exists():
            total_missing_dirs += 1
            console.print(f"[yellow]跳過缺失目錄：{source_dir}[/yellow]")
            continue

        files = sorted(source_dir.rglob("*.md"))
        imported = 0
        skipped = 0
        total_chunks = len(files)

        for file_idx, file_path in enumerate(files):
            metadata, content = parse_markdown_with_metadata(file_path)
            if _should_skip_rebuild_file(metadata, only_real):
                skipped += 1
                continue

            metadata.setdefault("title", file_path.stem)
            metadata.setdefault("doc_type", "unknown")
            doc_id = kb.make_deterministic_id(file_path.stem, collection)
            saved_id = kb.upsert_document(
                doc_id,
                content,
                _sanitize_metadata(metadata),
                collection_name=collection,
                full_document=_load_full_document(kb, file_path, content),
                chunk_index=file_idx,
                total_chunks=total_chunks,
            )
            if saved_id:
                imported += 1

        total_imported += imported
        total_skipped += skipped
        console.print(
            f"[green]{collection}[/green]：重建 {imported} 筆"
            + (f" / 跳過 {skipped} 筆" if skipped else "")
        )

    console.print(
        f"[bold]重建完成：總計 {total_imported} 筆"
        + (f" / 跳過 {total_skipped} 筆" if total_skipped else "")
        + (f" / 缺目錄 {total_missing_dirs} 個" if total_missing_dirs else "")
        + "[/bold]"
    )
    console.print(f"目前資料庫統計：{kb.get_stats()}")


@app.command("fetch-debates")
def fetch_debates(
    output_dir: str = typer.Option("./kb_data/policies/legislative_debates", help="輸出目錄"),
    limit: int = typer.Option(30, help="最大質詢紀錄數量"),
    do_ingest: bool = typer.Option(False, "--ingest", "-I", help="擷取後自動匯入知識庫"),
) -> None:
    """從立法院 g0v API 擷取質詢與會議紀錄（Level B 來源）。"""
    from src.knowledge.fetchers.legislative_debate_fetcher import LegislativeDebateFetcher

    fetcher = LegislativeDebateFetcher(output_dir=Path(output_dir), limit=limit)
    console.print(f"[bold]正在從{fetcher.name()}擷取資料...[/bold]")
    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")
    _maybe_ingest(results, do_ingest)


@app.command("fetch-procurement")
def fetch_procurement(
    output_dir: str = typer.Option("./kb_data/policies/procurement", help="輸出目錄"),
    days: int = typer.Option(7, help="擷取最近 N 天的採購公告"),
    limit: int = typer.Option(50, help="最大公告數量"),
    keyword: str = typer.Option("", help="搜尋關鍵字（空白則依日期列出）"),
    do_ingest: bool = typer.Option(False, "--ingest", "-I", help="擷取後自動匯入知識庫"),
) -> None:
    """從 g0v 採購 API 擷取政府採購公告（Level B 來源）。"""
    from src.knowledge.fetchers.procurement_fetcher import ProcurementFetcher

    fetcher = ProcurementFetcher(output_dir=Path(output_dir), days=days, limit=limit, keyword=keyword)
    console.print(f"[bold]正在從{fetcher.name()}擷取資料...[/bold]")
    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")
    _maybe_ingest(results, do_ingest)


@app.command("fetch-judicial")
def fetch_judicial(
    output_dir: str = typer.Option("./kb_data/regulations/judicial", help="輸出目錄"),
    limit: int = typer.Option(20, help="最大裁判書數量"),
    do_ingest: bool = typer.Option(False, "--ingest", "-I", help="擷取後自動匯入知識庫"),
) -> None:
    """從司法院裁判書 API 擷取裁判書全文（Level A 來源）。"""
    from src.knowledge.fetchers.judicial_fetcher import JudicialFetcher

    fetcher = JudicialFetcher(output_dir=Path(output_dir), limit=limit)
    console.print(f"[bold]正在從{fetcher.name()}擷取資料...[/bold]")
    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")
    _maybe_ingest(results, do_ingest)


@app.command("fetch-interpretations")
def fetch_interpretations(
    output_dir: str = typer.Option("./kb_data/regulations/interpretations", help="輸出目錄"),
    limit: int = typer.Option(30, help="最大函釋數量"),
    keyword: str = typer.Option("", help="搜尋關鍵字（可選）"),
    do_ingest: bool = typer.Option(False, "--ingest", "-I", help="擷取後自動匯入知識庫"),
) -> None:
    """從法務部主管法規查詢系統擷取行政函釋（Level A 來源）。"""
    from src.knowledge.fetchers.interpretation_fetcher import InterpretationFetcher

    fetcher = InterpretationFetcher(output_dir=Path(output_dir), limit=limit, keyword=keyword)
    console.print(f"[bold]正在從{fetcher.name()}擷取資料...[/bold]")
    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")
    _maybe_ingest(results, do_ingest)


@app.command("fetch-local")
def fetch_local(
    output_dir: str = typer.Option("./kb_data/regulations/local", help="輸出目錄"),
    city: str = typer.Option("taipei", help="城市代碼（如 taipei）"),
    limit: int = typer.Option(30, help="最大法規數量"),
    do_ingest: bool = typer.Option(False, "--ingest", "-I", help="擷取後自動匯入知識庫"),
) -> None:
    """從地方法規查詢系統擷取地方自治法規（Level A 來源）。"""
    from src.knowledge.fetchers.local_regulation_fetcher import LocalRegulationFetcher

    fetcher = LocalRegulationFetcher(output_dir=Path(output_dir), city=city, limit=limit)
    console.print(f"[bold]正在從{fetcher.name()}擷取資料...[/bold]")
    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")
    _maybe_ingest(results, do_ingest)


@app.command("fetch-examyuan")
def fetch_examyuan(
    output_dir: str = typer.Option("./kb_data/regulations/exam_yuan", help="輸出目錄"),
    limit: int = typer.Option(30, help="最大法規數量"),
    do_ingest: bool = typer.Option(False, "--ingest", "-I", help="擷取後自動匯入知識庫"),
) -> None:
    """從考試院法規資料庫擷取人事法規（Level B 來源）。"""
    from src.knowledge.fetchers.exam_yuan_fetcher import ExamYuanFetcher

    fetcher = ExamYuanFetcher(output_dir=Path(output_dir), limit=limit)
    console.print(f"[bold]正在從{fetcher.name()}擷取資料...[/bold]")
    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")
    _maybe_ingest(results, do_ingest)


@app.command("fetch-statistics")
def fetch_statistics(
    output_dir: str = typer.Option("./kb_data/policies/statistics", help="輸出目錄"),
    limit: int = typer.Option(10, help="最大統計通報數量"),
    do_ingest: bool = typer.Option(False, "--ingest", "-I", help="擷取後自動匯入知識庫"),
) -> None:
    """從主計總處統計發布訊息擷取統計通報（Level B 來源）。"""
    from src.knowledge.fetchers.statistics_fetcher import StatisticsFetcher

    fetcher = StatisticsFetcher(output_dir=Path(output_dir), limit=limit)
    console.print(f"[bold]正在從{fetcher.name()}擷取資料...[/bold]")
    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")
    _maybe_ingest(results, do_ingest)


@app.command("fetch-controlyuan")
def fetch_controlyuan(
    output_dir: str = typer.Option("./kb_data/policies/control_yuan", help="輸出目錄"),
    limit: int = typer.Option(20, help="最大糾正案數量"),
    do_ingest: bool = typer.Option(False, "--ingest", "-I", help="擷取後自動匯入知識庫"),
) -> None:
    """從監察院擷取糾正案文（Level A 來源）。"""
    from src.knowledge.fetchers.control_yuan_fetcher import ControlYuanFetcher

    fetcher = ControlYuanFetcher(output_dir=Path(output_dir), limit=limit)
    console.print(f"[bold]正在從{fetcher.name()}擷取資料...[/bold]")
    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")
    _maybe_ingest(results, do_ingest)


def _run_fetcher_for_source(source_name: str):
    """根據來源名稱建立並執行對應的 fetcher。"""
    from src.knowledge.fetchers.constants import DEFAULT_LAW_PCODES
    from src.knowledge.fetchers.exam_yuan_fetcher import ExamYuanFetcher
    from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher
    from src.knowledge.fetchers.interpretation_fetcher import InterpretationFetcher
    from src.knowledge.fetchers.judicial_fetcher import JudicialFetcher
    from src.knowledge.fetchers.law_fetcher import LawFetcher
    from src.knowledge.fetchers.local_regulation_fetcher import LocalRegulationFetcher

    if source_name == "全國法規":
        return LawFetcher(output_dir=Path("./kb_data/regulations/laws"), pcodes=DEFAULT_LAW_PCODES).fetch()
    if source_name == "行政院公報":
        return GazetteFetcher(output_dir=Path("./kb_data/examples/gazette"), days=7).fetch()
    if source_name == "司法院判決":
        return JudicialFetcher(output_dir=Path("./kb_data/regulations/judicial")).fetch()
    if source_name == "法務部函釋":
        return InterpretationFetcher(output_dir=Path("./kb_data/regulations/interpretations")).fetch()
    if source_name == "地方法規":
        return LocalRegulationFetcher(output_dir=Path("./kb_data/regulations/local")).fetch()
    if source_name == "考試院法規":
        return ExamYuanFetcher(output_dir=Path("./kb_data/regulations/exam_yuan")).fetch()
    return None
