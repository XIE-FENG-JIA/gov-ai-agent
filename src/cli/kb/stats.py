import json
import logging
import os
from pathlib import Path

import typer
from rich.table import Table

from ._shared import app, console

logger = logging.getLogger(__name__)
_KB_STATS_EXCEPTIONS = (
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


def _log_stats_warning(action: str, exc: Exception) -> None:
    """記錄可預期的 CLI 降級錯誤。"""
    logger.warning("%s 失敗: %s", action, exc)


@app.command("list-docs")
def list_docs(
    collection: str = typer.Option("all", "--collection", "-c", help="集合名稱（examples/regulations/policies/all）"),
    limit: int = typer.Option(50, "--limit", "-n", help="最大顯示數量"),
) -> None:
    """列出知識庫中所有文件的詳細資訊。"""
    from . import _init_kb

    kb = _init_kb()
    if not kb.is_available:
        console.print("[red]錯誤：知識庫不可用。[/red]")
        raise typer.Exit(1)

    collection_map = {
        "examples": ("examples", kb.examples_collection),
        "regulations": ("regulations", kb.regulations_collection),
        "policies": ("policies", kb.policies_collection),
    }
    if collection == "all":
        targets = list(collection_map.values())
    elif collection in collection_map:
        targets = [collection_map[collection]]
    else:
        console.print(f"[red]錯誤：未知集合 '{collection}'，請使用 examples/regulations/policies/all[/red]")
        raise typer.Exit(1)

    table = Table(title="知識庫文件清單", show_lines=True)
    table.add_column("#", style="dim", no_wrap=True, width=4)
    table.add_column("集合", style="cyan", no_wrap=True, width=12)
    table.add_column("ID", style="dim", max_width=20)
    table.add_column("標題", style="green")
    table.add_column("類型", style="magenta", width=8)

    row_num = 0
    for coll_name, coll in targets:
        try:
            data = coll.get(include=["metadatas"])
            ids = data.get("ids", []) if data else []
            metadatas = data.get("metadatas", []) if data else []
            for index, doc_id in enumerate(ids):
                if row_num >= limit:
                    break
                meta = metadatas[index] if index < len(metadatas) else {}
                row_num += 1
                table.add_row(
                    str(row_num),
                    coll_name,
                    doc_id[:16] + "...",
                    meta.get("title", "無標題") if isinstance(meta, dict) else "無標題",
                    meta.get("doc_type", "-") if isinstance(meta, dict) else "-",
                )
        except _KB_STATS_EXCEPTIONS as exc:
            _log_stats_warning(f"讀取集合 {coll_name}", exc)
            console.print(f"[yellow]讀取集合 '{coll_name}' 時發生錯誤：{exc}[/yellow]")

    if row_num == 0:
        console.print("[yellow]知識庫目前為空。[/yellow]")
        return
    console.print(table)
    console.print(f"共顯示 {row_num} 筆文件")


@app.command("delete")
def delete_doc(
    doc_id: str = typer.Option(..., "--id", help="要刪除的文件 ID"),
    collection: str = typer.Option("examples", "--collection", "-c", help="文件所在集合（examples/regulations/policies）"),
) -> None:
    """從知識庫刪除單筆文件。"""
    from . import _init_kb

    kb = _init_kb()
    if not kb.is_available:
        console.print("[red]錯誤：知識庫不可用。[/red]")
        raise typer.Exit(1)

    coll = {
        "examples": kb.examples_collection,
        "regulations": kb.regulations_collection,
        "policies": kb.policies_collection,
    }.get(collection)
    if not coll:
        console.print(f"[red]錯誤：未知集合 '{collection}'，請使用 examples/regulations/policies[/red]")
        raise typer.Exit(1)

    try:
        existing = coll.get(ids=[doc_id])
        if not existing or not existing.get("ids"):
            console.print(f"[red]錯誤：在集合 '{collection}' 中找不到 ID '{doc_id}'[/red]")
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except _KB_STATS_EXCEPTIONS as exc:
        _log_stats_warning(f"查詢集合 {collection} 文件 {doc_id}", exc)
        console.print(f"[red]查詢失敗：{exc}[/red]")
        raise typer.Exit(1)

    try:
        coll.delete(ids=[doc_id])
        kb.invalidate_cache()
        console.print(f"[green]已從 '{collection}' 刪除文件 {doc_id}[/green]")
    except _KB_STATS_EXCEPTIONS as exc:
        _log_stats_warning(f"刪除集合 {collection} 文件 {doc_id}", exc)
        console.print(f"[red]刪除失敗：{exc}[/red]")
        raise typer.Exit(1)


@app.command("collections")
def list_collections() -> None:
    """列出知識庫中所有集合及其文件數量。"""
    from . import _init_kb

    kb = _init_kb()
    if not kb.is_available:
        console.print("[red]錯誤：知識庫不可用。[/red]")
        raise typer.Exit(1)

    try:
        colls = kb.client.list_collections()
    except _KB_STATS_EXCEPTIONS as exc:
        _log_stats_warning("列出知識庫集合", exc)
        console.print(f"[red]無法列出集合：{exc}[/red]")
        raise typer.Exit(1)

    table = Table(title="ChromaDB 集合清單", show_lines=True)
    table.add_column("集合名稱", style="cyan")
    table.add_column("文件數量", style="magenta", justify="right")
    table.add_column("metadata", style="dim")

    total = 0
    for collection in colls:
        count = collection.count()
        total += count
        table.add_row(collection.name, str(count), json.dumps(collection.metadata, ensure_ascii=False) if collection.metadata else "-")

    table.add_row("[bold]合計[/bold]", f"[bold]{total}[/bold]", "")
    console.print(table)


@app.command("details")
def details() -> None:
    """顯示知識庫的詳細統計資訊，包含儲存路徑和大小。"""
    from . import _init_kb

    kb = _init_kb()
    if not kb.is_available:
        console.print("[red]錯誤：知識庫不可用。[/red]")
        raise typer.Exit(1)

    persist_path = Path(kb.persist_path)
    total_size = 0
    if persist_path.exists():
        for file_path in persist_path.rglob("*"):
            if file_path.is_file():
                try:
                    total_size += file_path.stat().st_size
                except OSError:
                    pass

    if total_size >= 1024 * 1024:
        size_str = f"{total_size / (1024 * 1024):.2f} MB"
    elif total_size >= 1024:
        size_str = f"{total_size / 1024:.2f} KB"
    else:
        size_str = f"{total_size} B"

    stats = kb.get_stats()
    table = Table(title="知識庫詳細資訊", show_lines=True)
    table.add_column("項目", style="cyan", no_wrap=True)
    table.add_column("值", style="green")
    table.add_row("儲存路徑", str(persist_path.resolve()))
    table.add_row("儲存大小", size_str)
    table.add_row("examples 文件數", str(stats.get("examples_count", 0)))
    table.add_row("regulations 文件數", str(stats.get("regulations_count", 0)))
    table.add_row("policies 文件數", str(stats.get("policies_count", 0)))
    table.add_row("[bold]文件總數[/bold]", f"[bold]{sum(stats.values())}[/bold]")
    console.print(table)


@app.command("export-json")
def export_data(
    output_path: str = typer.Option("kb_export.json", "--output", "-o", help="匯出檔案路徑"),
) -> None:
    """將知識庫統計和文件清單匯出為 JSON。"""
    from . import _init_kb

    kb = _init_kb()
    if not kb.is_available:
        console.print("[red]錯誤：知識庫不可用。[/red]")
        raise typer.Exit(1)

    collections_info: dict[str, dict[str, object]] = {}
    for name, coll in [
        ("examples", kb.examples_collection),
        ("regulations", kb.regulations_collection),
        ("policies", kb.policies_collection),
    ]:
        try:
            data = coll.get(include=["metadatas"])
            ids = data.get("ids", []) if data else []
            metadatas = data.get("metadatas", []) if data else []
            collections_info[name] = {
                "count": len(ids),
                "documents": [
                    {"id": doc_id, "title": (metadatas[index] or {}).get("title", "無標題")}
                    for index, doc_id in enumerate(ids)
                ],
            }
        except _KB_STATS_EXCEPTIONS as exc:
            _log_stats_warning(f"匯出集合 {name}", exc)
            console.print(f"[dim]讀取集合 {name} 失敗：{exc}[/dim]")
            collections_info[name] = {"count": 0, "documents": []}

    export = {
        "persist_path": str(Path(kb.persist_path).resolve()),
        "stats": kb.get_stats(),
        "total_documents": sum(kb.get_stats().values()),
        "collections": collections_info,
    }
    out = Path(output_path)
    out.write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]已匯出至 {out.resolve()}[/green]")


@app.command(name="export")
def kb_export(
    output: str = typer.Option("kb_export.zip", "-o", "--output", help="匯出 ZIP 路徑"),
) -> None:
    """將知識庫資料匯出為 ZIP 壓縮檔。"""
    from . import ConfigManager

    try:
        kb_path = ConfigManager().config.get("knowledge_base", {}).get("path", "./kb_data")
    except _KB_STATS_EXCEPTIONS as exc:
        _log_stats_warning("載入知識庫匯出設定", exc)
        console.print(f"[dim]設定檔載入失敗，使用預設路徑：{exc}[/dim]")
        kb_path = "./kb_data"

    if not os.path.isdir(kb_path):
        console.print(f"[yellow]知識庫目錄不存在：{kb_path}[/yellow]")
        raise typer.Exit(1)

    import zipfile

    file_count = 0
    total_size = 0
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for root, _, files in os.walk(kb_path):
            for filename in files:
                file_path = os.path.join(root, filename)
                archive.write(file_path, os.path.relpath(file_path, kb_path))
                file_count += 1
                total_size += os.path.getsize(file_path)

    if file_count == 0:
        console.print("[yellow]知識庫為空，無資料可匯出。[/yellow]")
        try:
            os.remove(output)
        except OSError:
            pass
        return

    console.print(f"[green]已匯出 {file_count} 個檔案至 {output}[/green]")
    console.print(f"[dim]原始大小：{total_size:,} bytes → 壓縮後：{os.path.getsize(output):,} bytes[/dim]")
