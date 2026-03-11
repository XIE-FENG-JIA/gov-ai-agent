from pathlib import Path

import typer
from rich.console import Console

console = Console()


def highlight(
    file_path: str = typer.Argument(..., help="公文檔案路徑"),
    keywords: str = typer.Option(..., "--keywords", "-k", help="關鍵詞（逗號分隔）"),
    color: str = typer.Option("yellow", "--color", "-c", help="高亮顏色（yellow/red/green/blue）"),
):
    """標記公文中的關鍵詞並顯示統計。"""
    path = Path(file_path)
    if not path.exists():
        console.print("[red]錯誤：找不到檔案[/red]")
        raise typer.Exit(1)

    content = path.read_text(encoding="utf-8")
    kw_list = [k.strip() for k in keywords.split(",") if k.strip()]

    total = 0
    for kw in kw_list:
        total += content.count(kw)

    if total == 0:
        console.print("[yellow]未找到匹配[/yellow]")
        return

    # 用 Rich markup 標記關鍵詞
    _COLOR_MAP = {"yellow": "bold yellow", "red": "bold red", "green": "bold green", "blue": "bold blue"}
    markup = _COLOR_MAP.get(color.lower().strip(), "")
    if not markup:
        console.print(f"[yellow]未知的顏色：{color}（可用：yellow/red/green/blue），使用預設 yellow[/yellow]")
        markup = "bold yellow"

    highlighted = content
    for kw in kw_list:
        highlighted = highlighted.replace(kw, f"[{markup}]{kw}[/{markup}]")

    console.print(highlighted)
    console.print(f"\n[green]找到 {total} 個關鍵詞匹配[/green]")
