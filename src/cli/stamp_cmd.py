import os
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table

from src.cli.utils_io import atomic_text_write

console = Console()


def stamp(
    file_path: str = typer.Argument(..., help="要加蓋戳記的檔案路徑（.txt/.md）"),
    text: str = typer.Option("已核閱", "--text", "-t", help="戳記文字"),
    stamper: str = typer.Option("", "--stamper", "-s", help="戳記者姓名"),
    with_time: bool = typer.Option(True, "--with-time/--no-with-time", help="是否加時間戳記"),
    verify: bool = typer.Option(False, "--verify", help="驗證檔案是否已有戳記（不加蓋新戳記）"),
    position: str = typer.Option("bottom-right", "--position", help="戳記位置（top-right/bottom-right/bottom-center）"),
):
    """為公文檔案加蓋電子戳記。"""
    if not os.path.isfile(file_path):
        console.print(f"[red]錯誤：找不到檔案：{file_path}[/red]")
        raise typer.Exit(1)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as exc:
        console.print(f"[red]錯誤：無法讀取檔案：{exc}[/red]")
        raise typer.Exit(1)

    if verify:
        has_stamp = "[戳記]" in content
        if has_stamp:
            # 找出所有戳記行
            stamps = [line.strip() for line in content.split("\n") if "[戳記]" in line]
            console.print(f"[green]檔案已有 {len(stamps)} 個戳記：[/green]")
            for s in stamps:
                console.print(f"  {s}")
        else:
            console.print("[yellow]檔案尚未加蓋戳記。[/yellow]")
        return

    _POS_MAP = {"top-right": "右上角", "bottom-right": "右下角", "bottom-center": "下方置中"}
    pos_label = _POS_MAP.get(position.lower().strip(), "")
    if not pos_label:
        console.print(
            f"[yellow]未知的位置：{position}"
            "（可用：top-right/bottom-right/bottom-center），"
            "使用預設 bottom-right[/yellow]"
        )
        pos_label = "右下角"

    stamp_line = f"\n---\n[戳記] {text}"
    if pos_label:
        stamp_line += f" | 位置：{pos_label}"
    if stamper:
        stamp_line += f" | 戳記者：{stamper}"
    if with_time:
        stamp_line += f" | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    stamp_line += "\n"

    try:
        atomic_text_write(file_path, content + stamp_line)
    except OSError as exc:
        console.print(f"[red]錯誤：無法寫入檔案：{exc}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]已成功加蓋戳記至：{file_path}[/green]")
    console.print(f"  [dim]戳記位置：{pos_label}[/dim]")


def number(
    org: str = typer.Option("北市環", "--org", "-o", help="機關代碼"),
    year: int = typer.Option(0, "--year", "-y", help="民國年（0=自動取今年）"),
    seq: int = typer.Option(1, "--seq", "-s", help="流水號起始值"),
    count: int = typer.Option(1, "--count", "-c", help="產生幾組編號（1-100）"),
    fmt: str = typer.Option("standard", "--format", "-f", help="編號格式（standard/compact/full）"),
):
    """產生公文編號。"""
    if count < 1 or count > 100:
        console.print("[red]錯誤：count 必須在 1 到 100 之間[/red]")
        raise typer.Exit(1)

    if year == 0:
        year = datetime.now().year - 1911

    _FORMAT_MAP = {
        "standard": lambda o, y, s: f"{o}字第{y}{s:05d}號",
        "compact": lambda o, y, s: f"{o}{y}{s:05d}",
        "full": lambda o, y, s: f"（{o}）字第 {y} 年 {s:05d} 號",
    }
    formatter = _FORMAT_MAP.get(fmt.lower().strip())
    if formatter is None:
        console.print(f"[yellow]未知格式：{fmt}（可用：standard/compact/full）[/yellow]")
        formatter = _FORMAT_MAP["standard"]

    table = Table(title="公文編號")
    table.add_column("序號", justify="right")
    table.add_column("編號")

    for i in range(count):
        doc_number = formatter(org, year, seq + i)
        table.add_row(str(i + 1), doc_number)

    console.print(table)
    console.print(f"[green]已產生 {count} 組公文編號[/green]")
