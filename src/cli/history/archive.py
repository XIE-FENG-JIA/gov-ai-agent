"""Archive and record file commands for history."""

from __future__ import annotations

import difflib
import json
import os
import shutil
import time
from itertools import combinations

import typer
from rich.table import Table

from ._shared import _ARCHIVE_EXCLUDE, console, get_history_dir_path
from src.cli.utils import atomic_json_write


def duplicate(
    threshold: float = typer.Option(0.8, "--threshold", "-t", help="相似度門檻（0.0-1.0）"),
) -> None:
    """偵測可能重複的歷史記錄。"""
    history_dir = get_history_dir_path(for_write=False)
    if not os.path.isdir(history_dir):
        console.print("[yellow]找不到歷史記錄。[/yellow]")
        return

    records: list[tuple[str, str]] = []
    for filename in sorted(os.listdir(history_dir)):
        if not filename.endswith(".json") or filename == "tags.json":
            continue
        file_path = os.path.join(history_dir, filename)
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except (json.JSONDecodeError, OSError):
            continue
        subject = data.get("subject", "")
        if subject:
            records.append((filename, subject))

    if len(records) < 2:
        console.print("[green]未發現重複記錄。[/green]")
        return

    duplicates: list[tuple[str, str, str, str, float]] = []
    for (filename_a, subject_a), (filename_b, subject_b) in combinations(records, 2):
        ratio = difflib.SequenceMatcher(None, subject_a, subject_b).ratio()
        if ratio >= threshold:
            duplicates.append((filename_a, subject_a, filename_b, subject_b, ratio))

    if not duplicates:
        console.print("[green]未發現重複記錄。[/green]")
        return

    console.print(f"[yellow]發現 {len(duplicates)} 組可能重複：[/yellow]")
    table = Table(title="可能重複的記錄")
    table.add_column("檔案 A", style="cyan")
    table.add_column("主旨 A", style="white")
    table.add_column("檔案 B", style="cyan")
    table.add_column("主旨 B", style="white")
    table.add_column("相似度", style="yellow", justify="right")
    for filename_a, subject_a, filename_b, subject_b, ratio in duplicates:
        table.add_row(filename_a, subject_a, filename_b, subject_b, f"{ratio:.2f}")
    console.print(table)


def rename(
    record_id: str = typer.Argument(..., help="記錄 ID"),
    new_name: str = typer.Argument(..., help="新的備註/主旨"),
) -> None:
    """重新命名指定記錄的主旨。"""
    history_dir = get_history_dir_path(for_write=True)
    if not os.path.isdir(history_dir):
        console.print("[red]找不到歷史記錄目錄。[/red]")
        raise typer.Exit(1)

    record_path = os.path.join(history_dir, f"{record_id}.json")
    if not os.path.isfile(record_path):
        console.print(f"[red]找不到記錄 {record_id}。[/red]")
        raise typer.Exit(1)

    try:
        with open(record_path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        console.print("[red]記錄檔案損壞。[/red]")
        raise typer.Exit(1)

    data["subject"] = new_name
    atomic_json_write(record_path, data)
    console.print(f"[green]已重命名記錄 {record_id} 的主旨為「{new_name}」。[/green]")


def history_archive(
    days: int = typer.Option(30, "--days", "-d", help="封存超過 N 天的記錄"),
    yes: bool = typer.Option(False, "--yes", "-y", help="跳過確認"),
) -> None:
    """封存超過指定天數的歷史記錄。"""
    history_dir = get_history_dir_path(for_write=True)
    if not os.path.isdir(history_dir):
        console.print("[yellow]找不到歷史記錄[/yellow]")
        return

    cutoff = time.time() - days * 86400
    old_files: list[str] = []
    for filename in os.listdir(history_dir):
        if not filename.endswith(".json") or filename in _ARCHIVE_EXCLUDE:
            continue
        file_path = os.path.join(history_dir, filename)
        if os.path.isfile(file_path) and os.path.getmtime(file_path) < cutoff:
            old_files.append(filename)

    if not old_files:
        console.print("[green]無需封存[/green]")
        return

    if not yes:
        console.print(f"[yellow]找到 {len(old_files)} 筆可封存記錄[/yellow]")
        console.print("[dim]使用 --yes 確認封存。[/dim]")
        return

    archive_dir = os.path.join(history_dir, "archive")
    os.makedirs(archive_dir, exist_ok=True)
    for filename in old_files:
        shutil.move(os.path.join(history_dir, filename), os.path.join(archive_dir, filename))

    console.print(f"[green]已封存 {len(old_files)} 筆記錄[/green]")


def history_compare(
    id_a: str = typer.Argument(..., help="第一筆記錄 ID"),
    id_b: str = typer.Argument(..., help="第二筆記錄 ID"),
) -> None:
    """比較兩筆歷史記錄的差異。"""
    history_dir = get_history_dir_path(for_write=False)
    if not os.path.isdir(history_dir):
        console.print("[red]找不到歷史記錄目錄。[/red]")
        raise typer.Exit(1)

    path_a = os.path.join(history_dir, f"{id_a}.json")
    path_b = os.path.join(history_dir, f"{id_b}.json")
    for label, path in [("A", path_a), ("B", path_b)]:
        if not os.path.isfile(path):
            console.print(f"[red]找不到記錄 {label}：{path}[/red]")
            raise typer.Exit(1)

    with open(path_a, "r", encoding="utf-8") as file:
        rec_a = json.load(file)
    with open(path_b, "r", encoding="utf-8") as file:
        rec_b = json.load(file)

    table = Table(title=f"比較：{id_a} vs {id_b}")
    table.add_column("欄位", style="cyan")
    table.add_column(id_a, style="green")
    table.add_column(id_b, style="yellow")
    for field in ["subject", "doc_type", "score", "risk", "timestamp"]:
        value_a = str(rec_a.get(field, "—"))
        value_b = str(rec_b.get(field, "—"))
        style = "[red]" if value_a != value_b else ""
        table.add_row(field, f"{style}{value_a}", f"{style}{value_b}")

    console.print(table)
