import os
from datetime import datetime
from pathlib import Path

import typer
from rich.table import Table

from ._shared import app, console, logger


@app.command("list")
def list_kb() -> None:
    """列出知識庫統計資訊和各集合的文件數量。"""
    from . import _init_kb

    kb = _init_kb()
    if not kb.is_available:
        console.print("[red]錯誤：知識庫不可用。[/red]")
        console.print("[dim]提示：請確認知識庫路徑正確，並嘗試 'gov-ai kb ingest' 匯入資料。[/dim]")
        raise typer.Exit(1)

    stats = kb.get_stats()
    table = Table(title="知識庫統計", show_lines=True)
    table.add_column("集合名稱", style="cyan", no_wrap=True)
    table.add_column("文件數量", style="magenta", justify="right")
    table.add_column("說明", style="dim")
    table.add_row("examples", str(stats.get("examples_count", 0)), "公文範例（函、公告、簽等）")
    table.add_row("regulations", str(stats.get("regulations_count", 0)), "法規文件（Level A 權威來源）")
    table.add_row("policies", str(stats.get("policies_count", 0)), "政策文件（Level B 輔助來源）")
    total = sum(stats.values())
    table.add_row("[bold]合計[/bold]", f"[bold]{total}[/bold]", "")
    console.print(table)

    if total == 0:
        console.print("\n[yellow]知識庫目前為空。[/yellow]")
        console.print("[dim]建議執行以下命令匯入資料：[/dim]")
        console.print("[dim]  gov-ai kb ingest[/dim]")
        console.print("[dim]  gov-ai kb fetch-laws --ingest[/dim]")
        console.print("[dim]  gov-ai kb fetch-gazette --ingest[/dim]")


@app.command()
def info() -> None:
    """顯示知識庫資訊總覽。"""
    from . import ConfigManager

    try:
        kb_path = ConfigManager().config.get("knowledge_base", {}).get("path", "./kb_data")
    except (OSError, RuntimeError, ValueError) as exc:
        console.print(f"[dim]設定檔載入失敗，使用預設路徑：{exc}[/dim]")
        kb_path = "./kb_data"

    if not os.path.isdir(kb_path):
        console.print(f"[yellow]知識庫目錄不存在：{kb_path}[/yellow]")
        console.print("[dim]請先執行 gov-ai kb fetch-laws 匯入資料。[/dim]")
        return

    total_files = 0
    total_size = 0
    categories: dict[str, int] = {}
    latest_mtime = 0.0
    for root, _, files in os.walk(kb_path):
        for filename in files:
            file_path = os.path.join(root, filename)
            total_files += 1
            total_size += os.path.getsize(file_path)
            latest_mtime = max(latest_mtime, os.path.getmtime(file_path))
            rel = os.path.relpath(root, kb_path)
            category = rel.split(os.sep)[0] if rel != "." else "根目錄"
            categories[category] = categories.get(category, 0) + 1

    console.print(f"\n[bold cyan]知識庫路徑：[/bold cyan]{os.path.abspath(kb_path)}")
    console.print(f"[bold cyan]文件總數：[/bold cyan]{total_files}")
    console.print(f"[bold cyan]總大小：[/bold cyan]{total_size:,} bytes")
    if latest_mtime > 0:
        console.print(f"[bold cyan]最後更新：[/bold cyan]{datetime.fromtimestamp(latest_mtime).strftime('%Y-%m-%d %H:%M:%S')}")

    if categories:
        table = Table(title="各類別文件數")
        table.add_column("類別", style="cyan")
        table.add_column("文件數", style="green", justify="right")
        for category, count in sorted(categories.items()):
            table.add_row(category, str(count))
        console.print(table)


@app.command(name="stats-detail")
def stats_detail(
    kb_path: str = typer.Option("./kb_data", "--path", "-p", help="知識庫路徑"),
) -> None:
    """顯示知識庫目錄的詳細統計資訊。"""
    kb_dir = Path(kb_path)
    if not kb_dir.exists():
        console.print(f"[red]找不到知識庫：{kb_path}[/red]")
        raise typer.Exit(1)

    subdirs = [path for path in sorted(kb_dir.iterdir()) if path.is_dir()]
    if not subdirs:
        console.print("[yellow]知識庫為空，沒有任何子目錄。[/yellow]")
        return

    table = Table(title="知識庫統計", show_lines=True)
    table.add_column("目錄", style="cyan")
    table.add_column("檔案數", style="magenta", justify="right")
    table.add_column("大小 (KB)", style="green", justify="right")
    table.add_column("最後修改", style="dim")

    for subdir in subdirs:
        files = [file_path for file_path in subdir.rglob("*") if file_path.is_file()]
        stats = []
        for file_path in files:
            try:
                stats.append(file_path.stat())
            except OSError:
                continue
        last_modified = datetime.fromtimestamp(max(stat.st_mtime for stat in stats)).strftime("%Y-%m-%d %H:%M:%S") if stats else "-"
        table.add_row(subdir.name, str(len(files)), f"{sum(stat.st_size for stat in stats) / 1024:.1f}", last_modified)

    console.print(table)


@app.command(name="list-sources")
def list_sources(
    kb_path: str = typer.Option("./kb_data", "--path", "-p", help="知識庫路徑"),
) -> None:
    """列出知識庫中的所有來源檔案。"""
    if not os.path.isdir(kb_path):
        console.print(f"[red]找不到知識庫目錄：{kb_path}[/red]")
        raise typer.Exit(1)

    files = []
    for root, _, filenames in os.walk(kb_path):
        for filename in filenames:
            file_path = os.path.join(root, filename)
            files.append({"path": os.path.relpath(file_path, kb_path), "size": os.path.getsize(file_path)})

    if not files:
        console.print("[yellow]知識庫中尚無來源檔案。[/yellow]")
        return

    table = Table(title="知識庫來源檔案")
    table.add_column("檔案路徑", style="cyan")
    table.add_column("大小", style="green", justify="right")
    for file_info in sorted(files, key=lambda item: item["path"]):
        table.add_row(file_info["path"], f"{file_info['size']:,} bytes")
    console.print(table)
    console.print(f"\n[dim]共 {len(files)} 個檔案。[/dim]")


@app.command("staleness")
def check_staleness(
    level: str = typer.Option("", "--level", "-l", help="篩選來源等級（A 或 B）"),
    stale_only: bool = typer.Option(False, "--stale-only", help="只顯示過期或從未擷取的來源"),
) -> None:
    """顯示知識庫各資料來源的更新狀態。"""
    from src.knowledge.staleness import StalenessChecker

    sources = StalenessChecker().check_all()
    level_upper = level.strip().upper()
    if level_upper in ("A", "B"):
        sources = [source for source in sources if source.level == level_upper]
    if stale_only:
        sources = [source for source in sources if source.is_stale]
    if not sources:
        console.print("[green]✅ 所有來源資料均在有效期內。[/green]")
        return

    table = Table(title="知識庫資料來源狀態 (gov-ai kb staleness)", show_lines=True)
    for column, kwargs in [
        ("", {"width": 2}),
        ("來源", {"style": "cyan", "no_wrap": True}),
        ("Lv", {"width": 3}),
        ("上次更新", {"no_wrap": True}),
        ("已過", {"justify": "right"}),
        ("建議頻率", {"justify": "right"}),
        ("文件數", {"justify": "right"}),
        ("更新指令", {"style": "dim"}),
    ]:
        table.add_column(column, **kwargs)

    stale_count = 0
    never_count = 0
    for source in sources:
        if source.never_fetched:
            updated_str = "[dim]從未擷取[/dim]"
            days_str = "[dim]—[/dim]"
            never_count += 1
        elif source.is_stale:
            updated_str = source.last_updated.strftime("%Y-%m-%d") if source.last_updated else "—"
            days_str = f"[red]{source.days_since_update:.0f} 天[/red]"
            stale_count += 1
        else:
            updated_str = source.last_updated.strftime("%Y-%m-%d") if source.last_updated else "—"
            days_str = f"[green]{source.days_since_update:.0f} 天[/green]"
        table.add_row(
            source.status_icon,
            source.source_name,
            f"[{'yellow' if source.level == 'A' else 'blue'}]{source.level}[/{'yellow' if source.level == 'A' else 'blue'}]",
            updated_str,
            days_str,
            f"{source.max_age_days} 天",
            str(source.file_count),
            f"gov-ai kb {source.fetch_cmd}",
        )

    console.print(table)
    total_stale = stale_count + never_count
    if total_stale:
        console.print(f"\n[yellow]⚠ {total_stale} 個來源需要更新（{never_count} 個從未擷取，{stale_count} 個已過期）[/yellow]")
        console.print("[dim]執行 `gov-ai kb auto-update` 自動更新 Level A 來源[/dim]")
    else:
        console.print("\n[green]✅ 所有來源資料均在有效期內[/green]")


@app.command("auto-update")
def auto_update(
    max_age_days: int = typer.Option(0, "--max-age-days", help="強制更新超過 N 天的來源（0 = 使用各來源預設設定）"),
    dry_run: bool = typer.Option(False, "--dry-run", help="僅顯示哪些來源需要更新，不實際執行"),
    do_ingest: bool = typer.Option(False, "--ingest", "-I", help="更新後自動匯入知識庫"),
    level: str = typer.Option("A", "--level", "-l", help="只更新指定等級的來源（A=Level A 權威來源 / all=全部）"),
) -> None:
    """自動更新過期的知識庫資料來源。"""
    from src.knowledge.staleness import StalenessChecker
    from . import _init_kb
    from .rebuild import _run_fetcher_for_source
    from .corpus import _ingest_fetch_results

    stale = StalenessChecker().get_stale(max_age_days=max_age_days if max_age_days > 0 else None)
    level_upper = level.strip().upper()
    if level_upper == "A":
        stale = [source for source in stale if source.level == "A"]
    if not stale:
        console.print("[green]✅ 沒有需要更新的資料來源。[/green]")
        return

    auto_list = [source for source in stale if source.is_auto_updatable]
    manual_list = [source for source in stale if not source.is_auto_updatable]
    console.print(f"\n[bold]需要更新的來源（共 {len(stale)} 個）：[/bold]")
    for source in stale:
        status_desc = "從未擷取" if source.never_fetched else f"最後更新 {source.days_since_update:.0f} 天前"
        console.print(f"  {source.status_icon} [cyan]{source.source_name}[/cyan] — {status_desc}{'' if source.is_auto_updatable else ' [dim][需手動][/dim]'}")

    if dry_run:
        console.print(f"\n[dim]--dry-run 模式。將自動更新 {len(auto_list)} 個，需手動更新 {len(manual_list)} 個。[/dim]")
        if manual_list:
            console.print("\n[dim]手動更新指令：[/dim]")
            for source in manual_list:
                console.print(f"  gov-ai kb {source.fetch_cmd} --ingest")
        return

    updated_count = 0
    failed_count = 0
    for source in auto_list:
        console.print(f"\n[bold]正在更新：{source.source_name}...[/bold]")
        try:
            results = _run_fetcher_for_source(source.source_name)
            if results is None:
                console.print(f"  [yellow]⚠ {source.source_name}：找不到對應的 fetcher，請手動更新[/yellow]")
                failed_count += 1
                continue
            console.print(f"  [green]✅ 擷取完成：{len(results)} 個檔案[/green]")
            if do_ingest and results:
                kb = _init_kb()
                count = _ingest_fetch_results(results, kb)
                console.print(f"  [green]已匯入 {count} 筆至知識庫[/green]")
            updated_count += 1
        except (RuntimeError, OSError) as exc:
            console.print(f"  [red]❌ 更新失敗：{exc}[/red]")
            logger.exception("auto_update: %s 更新失敗", source.source_name)
            failed_count += 1

    if manual_list:
        console.print("\n[yellow]以下來源需手動更新（參數較多，請依需求調整）：[/yellow]")
        for source in manual_list:
            console.print(f"  gov-ai kb {source.fetch_cmd} --ingest")

    console.print(
        f"\n[bold]自動更新完成：成功 {updated_count} 個"
        + (f"，失敗 {failed_count} 個" if failed_count else "")
        + (f"，手動更新 {len(manual_list)} 個" if manual_list else "")
        + "[/bold]"
    )
