"""公文品質回饋記錄。

讓使用者對生成的公文給予品質評分與改進建議，並提供統計摘要。
"""
import json
import os
from collections import Counter
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()

_FEEDBACK_FILE = ".gov-ai-feedback.json"


def _get_feedback_path() -> str:
    return os.path.join(os.getcwd(), _FEEDBACK_FILE)


def _load_feedback() -> list[dict]:
    path = _get_feedback_path()
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_feedback(data: list[dict]) -> None:
    path = _get_feedback_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _score_color(score: int) -> str:
    if score <= 2:
        return "red"
    if score == 3:
        return "yellow"
    return "green"


@app.command(name="add")
def add(
    file: str = typer.Option("", "--file", "-f", help="公文檔案路徑（記錄用）"),
    score: int = typer.Option(..., "--score", "-s", help="品質評分 1-5", min=1, max=5),
    comment: str = typer.Option("", "--comment", "-c", help="改進建議"),
):
    """新增一筆品質回饋。"""
    record = {
        "timestamp": datetime.now().isoformat(),
        "file": file,
        "score": score,
        "comment": comment,
    }
    data = _load_feedback()
    data.append(record)
    _save_feedback(data)
    color = _score_color(score)
    console.print(f"[green]已新增回饋[/green]（評分：[{color}]{score}[/{color}]）")


@app.command(name="list")
def list_feedback(
    count: int = typer.Option(10, "--count", "-n", help="顯示最近 N 筆", min=1, max=100),
    sort_by: str = typer.Option("date", "--sort", "-s", help="排序方式（date/score）"),
):
    """列出最近的品質回饋。"""
    data = _load_feedback()
    if not data:
        console.print("[yellow]尚無回饋記錄。[/yellow]")
        raise typer.Exit()

    recent = data[-count:]
    recent.reverse()

    if sort_by.lower().strip() == "score":
        recent.sort(key=lambda x: x.get("score", 0), reverse=True)
        console.print("  [dim]排序方式：依評分排序[/dim]")
    elif sort_by.lower().strip() == "date":
        # 預設已按時間排序（最新在前）
        console.print("  [dim]排序方式：依日期排序[/dim]")
    else:
        console.print(f"[yellow]未知的排序方式：{sort_by}（可用：date/score）[/yellow]")

    table = Table(title=f"最近 {len(recent)} 筆回饋", show_lines=True)
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("時間", width=16)
    table.add_column("檔案", width=20)
    table.add_column("評分", width=6, justify="center")
    table.add_column("評語", width=30)

    for i, rec in enumerate(recent, 1):
        ts = rec.get("timestamp", "")[:16].replace("T", " ")
        fname = rec.get("file", "") or "-"
        sc = rec.get("score", 0)
        color = _score_color(sc)
        comment = rec.get("comment", "") or "-"
        table.add_row(str(i), ts, fname, f"[{color}]{sc}[/{color}]", comment)

    console.print(table)


@app.command(name="summary")
def summary():
    """顯示回饋統計摘要。"""
    data = _load_feedback()
    if not data:
        console.print("[yellow]尚無回饋記錄。[/yellow]")
        raise typer.Exit()

    scores = [r.get("score", 0) for r in data]
    total = len(scores)
    avg = sum(scores) / total

    console.print("\n[bold]回饋統計[/bold]")
    console.print(f"  總筆數：{total}")
    avg_color = _score_color(round(avg))
    console.print(f"  平均分數：[{avg_color}]{avg:.1f}[/{avg_color}]")

    # 分數分布
    dist = Counter(scores)
    console.print("\n  分數分布：")
    for s in range(1, 6):
        cnt = dist.get(s, 0)
        bar = "█" * cnt
        color = _score_color(s)
        console.print(f"    {s} 分：[{color}]{bar}[/{color}] ({cnt})")

    # 關鍵字統計
    comments = [r.get("comment", "") for r in data if r.get("comment")]
    if comments:
        words: Counter = Counter()
        for c in comments:
            # 簡單中文分詞：以標點和空白切分，取長度 >= 2 的詞
            tokens = []
            buf = ""
            for ch in c:
                if ch.isalnum() or "\u4e00" <= ch <= "\u9fff":
                    buf += ch
                else:
                    if len(buf) >= 2:
                        tokens.append(buf)
                    buf = ""
            if len(buf) >= 2:
                tokens.append(buf)
            words.update(tokens)

        if words:
            top = words.most_common(5)
            console.print("\n  常見關鍵字：")
            for word, cnt in top:
                console.print(f"    {word}（{cnt} 次）")

    console.print()


@app.command(name="stats")
def feedback_stats(
    feedback_dir: str = typer.Option(
        ".feedback", "--dir", "-d", help="回饋目錄"
    ),
):
    """掃描回饋目錄中的 JSON 檔案並顯示統計摘要。"""
    if not os.path.isdir(feedback_dir):
        console.print("[red]找不到回饋目錄[/red]")
        raise typer.Exit(code=1)

    json_files = [
        f for f in os.listdir(feedback_dir) if f.endswith(".json")
    ]
    records: list[dict] = []
    for fname in sorted(json_files):
        fpath = os.path.join(feedback_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                rec = json.load(f)
            if isinstance(rec, dict):
                records.append(rec)
        except (json.JSONDecodeError, OSError):
            continue

    if not records:
        console.print("[yellow]無回饋記錄[/yellow]")
        raise typer.Exit()

    scores = [r.get("score", 0) for r in records]
    categories = [r.get("category", "未分類") for r in records if r.get("category")]
    total = len(records)
    avg = sum(scores) / total

    table = Table(title="回饋統計", show_lines=True)
    table.add_column("項目", style="bold", width=16)
    table.add_column("數值", width=20)
    table.add_row("總筆數", str(total))
    table.add_row("平均分數", f"{avg:.1f}")

    # 分數區間分布
    dist = Counter(scores)
    dist_parts = []
    for s in sorted(dist.keys()):
        dist_parts.append(f"{s} 分：{dist[s]} 筆")
    table.add_row("分數分布", "\n".join(dist_parts))

    # 類別統計
    if categories:
        cat_dist = Counter(categories)
        cat_parts = []
        for cat, cnt in cat_dist.most_common():
            cat_parts.append(f"{cat}：{cnt} 筆")
        table.add_row("類別分布", "\n".join(cat_parts))

    console.print(table)


@app.command(name="export")
def feedback_export(
    output: str = typer.Option("feedback_export.csv", "-o", "--output", help="匯出路徑"),
):
    """匯出回饋記錄為 CSV 檔案。"""
    import csv
    data = _load_feedback()
    if not data:
        console.print("[yellow]尚無回饋記錄可匯出。[/yellow]")
        raise typer.Exit()

    fieldnames = ["timestamp", "file", "score", "comment"]
    with open(output, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for rec in data:
            writer.writerow({k: rec.get(k, "") for k in fieldnames})

    console.print(f"[green]已匯出 {len(data)} 筆回饋至 {output}[/green]")
