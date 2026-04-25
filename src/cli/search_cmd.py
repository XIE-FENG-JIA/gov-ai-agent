"""搜尋已生成的公文記錄。"""

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from src.cli.utils_io import JSONStore

console = Console(width=120)
_history_store = JSONStore(".gov-ai-history.json", default=[])


def search(
    keyword: str = typer.Argument(..., help="搜尋關鍵字"),
    doc_type: str = typer.Option("", "--type", "-t", help="篩選公文類型"),
    limit: int = typer.Option(20, "--limit", "-n", help="最大顯示筆數"),
    export: str = typer.Option("", "--export", "-e", help="匯出搜尋結果至 JSON 檔案"),
):
    """搜尋生成歷史中包含關鍵字的公文記錄。"""
    if not _history_store.exists():
        console.print("[yellow]尚無生成記錄。[/yellow]")
        raise typer.Exit()

    history = _history_store.load()
    if not isinstance(history, list):
        console.print("[red]歷史記錄檔案損壞。[/red]")
        raise typer.Exit(1)

    results = []
    for rec in history:
        input_text = rec.get("input", "")
        rec_type = rec.get("doc_type", "")
        if keyword not in input_text and keyword not in rec_type:
            continue
        if doc_type and doc_type != rec_type:
            continue
        results.append(rec)

    if not results:
        console.print(f"[yellow]找不到包含 '{keyword}' 的記錄。[/yellow]")
        raise typer.Exit()

    results = results[-limit:]

    table = Table(title=f"搜尋結果：'{keyword}'（共 {len(results)} 筆）", show_lines=True)
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("時間", width=16)
    table.add_column("類型", width=6, justify="center")
    table.add_column("需求摘要", width=40)
    table.add_column("分數", width=6, justify="center")
    table.add_column("輸出", width=20)

    for i, rec in enumerate(results, 1):
        ts = rec.get("timestamp", "")[:16].replace("T", " ")
        rtype = rec.get("doc_type", "?")
        summary = rec.get("input", "")[:40]
        score = rec.get("score")
        score_str = f"{score:.2f}" if score is not None else "-"
        output = rec.get("output", "")
        table.add_row(str(i), ts, rtype, summary, score_str, output)

    console.print(table)

    if export:
        with open(export, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        console.print(f"[green]已匯出 {len(results)} 筆搜尋結果至：{export}[/green]")


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

