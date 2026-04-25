from datetime import date
from pathlib import Path

import typer

from src.cli.verify_cmd import collect_citation_verification_checks, render_citation_verification_results
from src.sources.ingest import _adapter_registry
from src.sources.quality_gate import QualityGate, QualityGateError

from ._shared import app, console
from .corpus import _ingest_fetch_results, _load_full_document, _sanitize_metadata, parse_markdown_with_metadata
from ._quality_gate_cli import (
    load_gate_check_records,
    render_gate_check_failure,
    render_gate_check_success,
    run_corpus_quality_gate,
)
from ._rebuild_corpus import REBUILD_COLLECTIONS, rebuild_active_corpus, should_skip_rebuild_file


@app.command("rebuild")
def rebuild(
    base_dir: str = typer.Option("./kb_data", "--base-dir", help="知識來源根目錄"),
    only_real: bool = typer.Option(
        False,
        "--only-real",
        help="只重建真實來源文件（跳過 synthetic / fixture_fallback）",
    ),
    quality_gate: bool = typer.Option(
        False,
        "--quality-gate",
        help="先對 active corpus 的每個來源批次跑 quality gate，再進行 only-real 重建",
    ),
    verify_docx: str | None = typer.Option(
        None,
        "--verify-docx",
        help="only-real 重建後立刻驗證指定 DOCX 的 citation metadata 仍能對回 active corpus",
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

    effective_only_real = only_real or quality_gate

    if verify_docx and not effective_only_real:
        console.print("[red]錯誤：--verify-docx 只能搭配 --only-real 使用。[/red]")
        raise typer.Exit(1)

    corpus_root = source_root / "corpus"
    if quality_gate and not (corpus_root.exists() and any(corpus_root.rglob("*.md"))):
        console.print(
            "[red]錯誤：--quality-gate 需要 kb_data/corpus active corpus，"
            "不能退回 legacy collections。[/red]"
        )
        raise typer.Exit(1)

    if effective_only_real and corpus_root.exists() and any(corpus_root.rglob("*.md")):
        if quality_gate:
            reports = run_corpus_quality_gate(corpus_root)
            for report in reports:
                console.print(
                    "[bold green]quality gate: PASS[/bold green] "
                    f"adapter={report.adapter} records_in={report.records_in} records_out={report.records_out}"
                )
        total_imported, skipped_by_reason = rebuild_active_corpus(kb, corpus_root)
        total_skipped = sum(skipped_by_reason.values())
        console.print(
            f"[bold]重建完成：總計 {total_imported} 筆"
            + (f" / 跳過 {total_skipped} 筆" if total_skipped else "")
            + "[/bold]"
        )
        if verify_docx:
            try:
                checks = collect_citation_verification_checks(Path(verify_docx), corpus_root)
            except FileNotFoundError:
                console.print(f"[red]錯誤：找不到檔案 {verify_docx}[/red]")
                raise typer.Exit(1)
            except ValueError as exc:
                console.print(f"[red]錯誤：{exc}[/red]")
                raise typer.Exit(1)

            passed, total = render_citation_verification_results(
                checks,
                title="Only-real 重建後驗證",
            )
            console.print(f"[bold cyan]only-real post-rebuild verify：通過 {passed}/{total} 項[/bold cyan]")
            if passed != total:
                raise typer.Exit(1)
        console.print(f"目前資料庫統計：{kb.get_stats()}")
        return
    if effective_only_real:
        console.print("[yellow]only-real 模式未找到 kb_data/corpus，退回 legacy collections 重建。[/yellow]")

    total_imported = 0
    total_skipped = 0
    total_missing_dirs = 0

    for collection, subdir_name in REBUILD_COLLECTIONS:
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
            if should_skip_rebuild_file(metadata, only_real):
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


from .fetch_commands import _run_fetcher_for_source  # re-export for compatibility

@app.command("gate-check")
def gate_check(
    source: str = typer.Option(..., "--source", "-s", help="來源代碼，例如 mojlaw / datagovtw / mohw"),
    since: str | None = typer.Option(None, "--since", help="ISO 日期過濾，例如 2026-01-01"),
    limit: int = typer.Option(10, "--limit", min=1, help="最多檢查幾筆文件"),
    output_format: str = typer.Option("human", "--format", help="輸出格式：human 或 json"),
) -> None:
    """Probe one public source through the live-ingest quality gate."""

    source_key = source.strip().lower()
    registry = _adapter_registry()
    if source_key not in registry:
        raise typer.BadParameter(f"不支援的來源：{source}。可用來源：{', '.join(sorted(registry))}")
    if output_format not in {"human", "json"}:
        raise typer.BadParameter("--format 只支援 human 或 json")

    try:
        since_date = date.fromisoformat(since) if since else None
    except ValueError as exc:
        raise typer.BadParameter("日期格式必須是 YYYY-MM-DD") from exc

    records = load_gate_check_records(source_key, registry=registry, since_date=since_date, limit=limit)
    gate = QualityGate.from_adapter_name(source_key)

    try:
        report = gate.evaluate(records, adapter_name=source_key)
    except QualityGateError as exc:
        render_gate_check_failure(exc, adapter_name=source_key, records_in=len(records), output_format=output_format)
        raise typer.Exit(code=1) from exc

    render_gate_check_success(report, output_format=output_format)
    if report.pass_rate < 0.5:
        raise typer.Exit(code=1)
