"""Tag commands for history records."""

from __future__ import annotations

import typer
from rich.table import Table

from ._shared import console, load_tags, save_tags


def tag_add(
    record_id: str = typer.Argument(..., help="記錄 ID"),
    tag: str = typer.Argument(..., help="標籤名稱"),
) -> None:
    """為指定記錄加入標籤。"""
    tags = load_tags()
    if record_id not in tags:
        tags[record_id] = []
    if tag not in tags[record_id]:
        tags[record_id].append(tag)
    save_tags(tags)
    console.print(f"[green]已加入標籤「{tag}」至記錄 {record_id}。[/green]")


def tag_remove(
    record_id: str = typer.Argument(..., help="記錄 ID"),
    tag: str = typer.Argument(..., help="標籤名稱"),
) -> None:
    """移除指定記錄的標籤。"""
    tags = load_tags()
    if record_id in tags and tag in tags[record_id]:
        tags[record_id].remove(tag)
        if not tags[record_id]:
            del tags[record_id]
        save_tags(tags)
        console.print(f"[green]已移除記錄 {record_id} 的標籤「{tag}」。[/green]")
        return
    console.print(f"[yellow]未找到標籤「{tag}」於記錄 {record_id}。[/yellow]")


def tag_list(
    record_id: str = typer.Option("", help="查詢特定記錄的標籤"),
) -> None:
    """列出標籤。"""
    tags = load_tags()
    if not tags:
        console.print("[yellow]無標籤。[/yellow]")
        return

    if record_id:
        record_tags = tags.get(record_id, [])
        if not record_tags:
            console.print(f"[yellow]記錄 {record_id} 無標籤。[/yellow]")
            return
        table = Table(title=f"記錄 {record_id} 的標籤")
        table.add_column("標籤", style="cyan")
        for tag in record_tags:
            table.add_row(tag)
        console.print(table)
        return

    table = Table(title="所有標籤")
    table.add_column("記錄 ID", style="cyan")
    table.add_column("標籤", style="green")
    for rid, tag_list_value in tags.items():
        table.add_row(rid, ", ".join(tag_list_value))
    console.print(table)
