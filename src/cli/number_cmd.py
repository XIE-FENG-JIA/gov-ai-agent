from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table

console = Console()


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
