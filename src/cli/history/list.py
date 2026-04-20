"""Listing, export, stats, search, and filter commands for history."""

from __future__ import annotations

import csv
import json

import typer
from rich.table import Table

from ._shared import _history_store, console, parse_date


def history_list(
    count: int = typer.Option(10, "--count", "-n", help="顯示最近 N 筆記錄", min=1, max=100),
    output_json: bool = typer.Option(False, "--json", help="以 JSON 格式輸出"),
) -> None:
    """列出最近的公文生成記錄。"""
    history = _history_store.load()

    if not history:
        if output_json:
            console.print(json.dumps([], ensure_ascii=False, indent=2))
            return
        console.print("[yellow]尚無生成記錄。[/yellow]")
        raise typer.Exit()

    recent = history[-count:]
    recent.reverse()

    if output_json:
        console.print(json.dumps(recent, ensure_ascii=False, indent=2))
        return

    table = Table(title=f"最近 {len(recent)} 筆生成記錄", show_lines=True)
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("時間", width=16)
    table.add_column("類型", width=6, justify="center")
    table.add_column("需求摘要", width=30)
    table.add_column("狀態", width=6, justify="center")
    table.add_column("分數", width=6, justify="center")
    table.add_column("耗時", width=8, justify="right")
    table.add_column("輸出", width=20)

    for index, rec in enumerate(recent, 1):
        ts = rec.get("timestamp", "")[:16].replace("T", " ")
        doc_type = rec.get("doc_type", "?")
        input_text = rec.get("input", "")[:28]
        status = rec.get("status", "?")
        status_str = "[green]✓[/green]" if status == "success" else "[red]✗[/red]"
        score = rec.get("score")
        score_str = f"{score:.2f}" if score is not None else "-"
        elapsed = rec.get("elapsed_sec")
        elapsed_str = f"{elapsed}s" if elapsed is not None else "-"
        output = rec.get("output", "")
        table.add_row(str(index), ts, doc_type, input_text, status_str, score_str, elapsed_str, output)

    console.print(table)
    console.print(f"[dim]共 {len(history)} 筆記錄（儲存於 {_history_store.path}）[/dim]")


def export_history(
    output: str = typer.Option("gov-ai-history.csv", "--output", "-o", help="匯出路徑"),
) -> None:
    """將生成歷史記錄匯出為 CSV 格式。"""
    history = _history_store.load()
    if not history:
        console.print("[yellow]尚無生成記錄可匯出。[/yellow]")
        raise typer.Exit()

    fieldnames = ["timestamp", "input_summary", "doc_type", "score", "risk", "elapsed", "output_path"]
    with open(output, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for rec in history:
            writer.writerow(
                {
                    "timestamp": rec.get("timestamp", ""),
                    "input_summary": rec.get("input", "")[:50],
                    "doc_type": rec.get("doc_type", ""),
                    "score": rec.get("score", ""),
                    "risk": rec.get("risk", ""),
                    "elapsed": rec.get("elapsed_sec", ""),
                    "output_path": rec.get("output", ""),
                }
            )

    console.print(f"[green]已匯出 {len(history)} 筆記錄至 {output}[/green]")


def export_csv(
    output: str = typer.Option("history_export.csv", "-o", "--output", help="CSV 輸出路徑"),
) -> None:
    """將歷史記錄匯出為 CSV 格式。"""
    records = _history_store.load()
    if not records:
        console.print("[yellow]尚無歷史記錄可匯出。[/yellow]")
        return

    fields = ["timestamp", "input", "doc_type", "output", "score", "risk"]
    with open(output, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field, "") for field in fields})

    console.print(f"[green]已匯出 {len(records)} 筆記錄至 {output}[/green]")


def history_stats() -> None:
    """顯示歷史生成記錄的統計分析。"""
    history = _history_store.load()
    if not history:
        console.print("[yellow]尚無生成記錄可統計。[/yellow]")
        raise typer.Exit()

    total = len(history)
    console.print(f"\n[bold]生成記錄統計[/bold]（共 {total} 筆）\n")

    type_counts: dict[str, int] = {}
    for rec in history:
        doc_type = rec.get("doc_type", "未知")
        type_counts[doc_type] = type_counts.get(doc_type, 0) + 1

    type_table = Table(title="公文類型分布")
    type_table.add_column("類型", justify="center")
    type_table.add_column("數量", justify="right")
    for doc_type, count in sorted(type_counts.items(), key=lambda item: item[1], reverse=True):
        type_table.add_row(doc_type, str(count))
    console.print(type_table)

    scores = [rec["score"] for rec in history if rec.get("score") is not None]
    if scores:
        console.print(f"\n平均品質分數：[bold cyan]{sum(scores) / len(scores):.2f}[/bold cyan]（{len(scores)} 筆有分數）")
    else:
        console.print("\n平均品質分數：[dim]無資料[/dim]")

    risk_counts: dict[str, int] = {}
    for rec in history:
        risk = rec.get("risk")
        if risk is not None:
            risk_counts[risk] = risk_counts.get(risk, 0) + 1
    if risk_counts:
        console.print(f"風險等級分布：{', '.join(f'{risk}: {count}' for risk, count in sorted(risk_counts.items()))}")
    else:
        console.print("風險等級分布：[dim]無資料[/dim]")

    times = [rec["elapsed_sec"] for rec in history if rec.get("elapsed_sec") is not None]
    if times:
        console.print(f"平均處理時間：[bold]{sum(times) / len(times):.1f}s[/bold]")
    else:
        console.print("平均處理時間：[dim]無資料[/dim]")


def history_search(
    query: str = typer.Option(..., "-q", "--query", help="搜尋關鍵字"),
    doc_type: str = typer.Option("", "--type", "-t", help="按公文類型篩選"),
) -> None:
    """搜尋歷史記錄。"""
    records = _history_store.load()
    if not records:
        console.print("[yellow]尚無歷史記錄。[/yellow]")
        return

    results = []
    for record in records:
        text_fields = f"{record.get('input', '')} {record.get('doc_type', '')} {record.get('output', '')}"
        if query.lower() in text_fields.lower():
            if doc_type and record.get("doc_type", "") != doc_type:
                continue
            results.append(record)

    if not results:
        console.print(f"[yellow]找不到符合「{query}」的記錄。[/yellow]")
        return

    table = Table(title=f"搜尋結果：{query}")
    table.add_column("時間", style="cyan", width=20)
    table.add_column("類型", style="yellow", width=8)
    table.add_column("輸入摘要", style="white")
    table.add_column("輸出", style="green")

    for record in results[-10:]:
        table.add_row(
            record.get("timestamp", "—")[:19],
            record.get("doc_type", "—"),
            record.get("input", "—")[:30],
            record.get("output", "—"),
        )

    console.print(table)
    console.print(f"\n[dim]共找到 {len(results)} 筆符合的記錄。[/dim]")


def history_clear(
    yes: bool = typer.Option(False, "--yes", "-y", help="跳過確認直接清除"),
    before: str = typer.Option("", "--before", help="清除此日期前的記錄（格式：YYYY-MM-DD）"),
    keep: int = typer.Option(0, "--keep", "-k", help="保留最近 N 筆記錄"),
) -> None:
    """清除生成歷史記錄。"""
    records = _history_store.load()
    if not records:
        console.print("[yellow]尚無歷史記錄可清除。[/yellow]")
        return

    remaining = records
    if before:
        try:
            cutoff = parse_date(before, field_label="錯誤：日期")
        except typer.Exit as exc:
            console.print("[red]錯誤：日期格式無效，請使用 YYYY-MM-DD。[/red]")
            raise typer.Exit(1) from exc
        remaining = [
            record
            for record in remaining
            if parse_date(record.get("timestamp", "9999-12-31")[:10], field_label="錯誤：日期") >= cutoff
        ]
    elif keep > 0:
        remaining = remaining[-keep:]
    else:
        remaining = []

    deleted_count = len(records) - len(remaining)
    if deleted_count == 0:
        console.print("[yellow]沒有符合條件的記錄需要清除。[/yellow]")
        return

    if not yes:
        console.print(f"[yellow]即將刪除 {deleted_count} 筆記錄（共 {len(records)} 筆）。[/yellow]")
        console.print("[dim]使用 --yes 跳過確認。[/dim]")
        raise typer.Exit(0)

    _history_store.save(remaining)
    console.print(f"[green]已清除 {deleted_count} 筆記錄，保留 {len(remaining)} 筆。[/green]")


def history_filter(
    doc_type: str = typer.Option("", "--type", "-t", help="按公文類型篩選"),
    score_min: float = typer.Option(0.0, "--score-min", help="最低分數篩選"),
    after: str = typer.Option("", "--after", help="此日期後的記錄（YYYY-MM-DD）"),
    before: str = typer.Option("", "--before", help="此日期前的記錄（YYYY-MM-DD）"),
) -> None:
    """依條件篩選歷史記錄。"""
    records = _history_store.load()
    if not records:
        console.print("[yellow]尚無歷史記錄。[/yellow]")
        return

    results = records
    if doc_type:
        results = [record for record in results if record.get("doc_type") == doc_type]
    if score_min > 0:
        results = [record for record in results if float(record.get("score", 0)) >= score_min]
    if after:
        cutoff = parse_date(after, field_label="日期")
        results = [record for record in results if parse_date(record.get("timestamp", "")[:10], field_label="日期") >= cutoff]
    if before:
        cutoff = parse_date(before, field_label="日期")
        results = [record for record in results if parse_date(record.get("timestamp", "")[:10], field_label="日期") <= cutoff]

    if not results:
        console.print("[yellow]沒有符合條件的記錄。[/yellow]")
        return

    table = Table(title="篩選結果")
    table.add_column("時間", style="cyan", width=20)
    table.add_column("類型", style="yellow", width=8)
    table.add_column("輸入", style="white")
    table.add_column("分數", style="green", justify="right")
    for record in results[-20:]:
        table.add_row(
            record.get("timestamp", "")[:19],
            record.get("doc_type", ""),
            record.get("input", "")[:30],
            str(record.get("score", "")),
        )
    console.print(table)
    console.print(f"\n[dim]共 {len(results)} 筆符合條件。[/dim]")
