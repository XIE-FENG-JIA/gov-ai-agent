"""搜尋已生成的公文記錄。"""

import json
import os

import typer
from rich.console import Console
from rich.table import Table

console = Console(width=120)
_HISTORY_FILE = ".gov-ai-history.json"


def search(
    keyword: str = typer.Argument(..., help="搜尋關鍵字"),
    doc_type: str = typer.Option("", "--type", "-t", help="篩選公文類型"),
    limit: int = typer.Option(20, "--limit", "-n", help="最大顯示筆數"),
    export: str = typer.Option("", "--export", "-e", help="匯出搜尋結果至 JSON 檔案"),
):
    """搜尋生成歷史中包含關鍵字的公文記錄。"""
    path = os.path.join(os.getcwd(), _HISTORY_FILE)
    if not os.path.isfile(path):
        console.print("[yellow]尚無生成記錄。[/yellow]")
        raise typer.Exit()

    try:
        with open(path, "r", encoding="utf-8") as f:
            history = json.load(f)
    except (json.JSONDecodeError, OSError):
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
