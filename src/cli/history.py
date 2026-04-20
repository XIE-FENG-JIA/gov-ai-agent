"""生成歷史記錄管理。

自動記錄每次公文生成的結果，供使用者查看和追蹤。
"""
import csv
import difflib
import json
import os
import shutil
import time
from datetime import datetime
from itertools import combinations

import typer
from rich.console import Console
from rich.table import Table

from src.cli.utils import JSONStore, atomic_json_write, resolve_state_path, resolve_state_read_path

app = typer.Typer()
console = Console()

_MAX_HISTORY = 100

# 共用 JSONStore 實例
_history_store = JSONStore(".gov-ai-history.json", default=[])
_tags_store = JSONStore(os.path.join(".history", "tags.json"), default={})
_pins_store = JSONStore(os.path.join(".history", "pins.json"), default=[])


def append_record(
    input_text: str,
    doc_type: str,
    output_path: str,
    score: float | None = None,
    risk: str | None = None,
    rounds_used: int | None = None,
    elapsed: float | None = None,
    status: str = "success",
) -> None:
    """新增一筆生成記錄。"""
    record = {
        "timestamp": datetime.now().isoformat(),
        "input": input_text[:200],
        "doc_type": doc_type,
        "output": output_path,
        "score": score,
        "risk": risk,
        "rounds_used": rounds_used,
        "elapsed_sec": round(elapsed, 1) if elapsed else None,
        "status": status,
    }
    history = _history_store.load()
    history.append(record)
    # 保留最近 N 筆
    if len(history) > _MAX_HISTORY:
        history = history[-_MAX_HISTORY:]

    try:
        _history_store.save(history)
    except OSError:
        pass  # 寫入失敗不影響主流程


@app.command(name="list")
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

    for i, rec in enumerate(recent, 1):
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

        table.add_row(str(i), ts, doc_type, input_text, status_str, score_str, elapsed_str, output)

    console.print(table)
    console.print(f"[dim]共 {len(history)} 筆記錄（儲存於 {_history_store.path}）[/dim]")


@app.command(name="export")
def export_history(
    output: str = typer.Option("gov-ai-history.csv", "--output", "-o", help="匯出路徑"),
) -> None:
    """將生成歷史記錄匯出為 CSV 格式。"""
    history = _history_store.load()

    if not history:
        console.print("[yellow]尚無生成記錄可匯出。[/yellow]")
        raise typer.Exit()

    fieldnames = ["timestamp", "input_summary", "doc_type", "score", "risk", "elapsed", "output_path"]

    with open(output, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in history:
            writer.writerow({
                "timestamp": rec.get("timestamp", ""),
                "input_summary": rec.get("input", "")[:50],
                "doc_type": rec.get("doc_type", ""),
                "score": rec.get("score", ""),
                "risk": rec.get("risk", ""),
                "elapsed": rec.get("elapsed_sec", ""),
                "output_path": rec.get("output", ""),
            })

    console.print(f"[green]已匯出 {len(history)} 筆記錄至 {output}[/green]")


@app.command(name="export-csv")
def export_csv(
    output: str = typer.Option("history_export.csv", "-o", "--output", help="CSV 輸出路徑"),
) -> None:
    """將歷史記錄匯出為 CSV 格式。"""
    records = _history_store.load()

    if not records:
        console.print("[yellow]尚無歷史記錄可匯出。[/yellow]")
        return

    fields = ["timestamp", "input", "doc_type", "output", "score", "risk"]

    with open(output, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            writer.writerow({k: r.get(k, "") for k in fields})

    console.print(f"[green]已匯出 {len(records)} 筆記錄至 {output}[/green]")


@app.command(name="stats")
def history_stats() -> None:
    """顯示歷史生成記錄的統計分析。"""
    history = _history_store.load()

    if not history:
        console.print("[yellow]尚無生成記錄可統計。[/yellow]")
        raise typer.Exit()

    total = len(history)
    console.print(f"\n[bold]生成記錄統計[/bold]（共 {total} 筆）\n")

    # 按 doc_type 分類計數
    type_counts: dict[str, int] = {}
    for rec in history:
        dt = rec.get("doc_type", "未知")
        type_counts[dt] = type_counts.get(dt, 0) + 1

    type_table = Table(title="公文類型分布")
    type_table.add_column("類型", justify="center")
    type_table.add_column("數量", justify="right")
    for dt, cnt in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        type_table.add_row(dt, str(cnt))
    console.print(type_table)

    # 平均品質分數
    scores = [rec["score"] for rec in history if rec.get("score") is not None]
    if scores:
        avg_score = sum(scores) / len(scores)
        console.print(f"\n平均品質分數：[bold cyan]{avg_score:.2f}[/bold cyan]（{len(scores)} 筆有分數）")
    else:
        console.print("\n平均品質分數：[dim]無資料[/dim]")

    # 風險等級分布
    risk_counts: dict[str, int] = {}
    for rec in history:
        risk = rec.get("risk")
        if risk is not None:
            risk_counts[risk] = risk_counts.get(risk, 0) + 1
    if risk_counts:
        risk_parts = [f"{r}: {c}" for r, c in sorted(risk_counts.items())]
        console.print(f"風險等級分布：{', '.join(risk_parts)}")
    else:
        console.print("風險等級分布：[dim]無資料[/dim]")

    # 平均處理時間
    times = [rec["elapsed_sec"] for rec in history if rec.get("elapsed_sec") is not None]
    if times:
        avg_time = sum(times) / len(times)
        console.print(f"平均處理時間：[bold]{avg_time:.1f}s[/bold]")
    else:
        console.print("平均處理時間：[dim]無資料[/dim]")


@app.command(name="search")
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
    for r in records:
        text_fields = f"{r.get('input', '')} {r.get('doc_type', '')} {r.get('output', '')}"
        if query.lower() in text_fields.lower():
            if doc_type and r.get("doc_type", "") != doc_type:
                continue
            results.append(r)

    if not results:
        console.print(f"[yellow]找不到符合「{query}」的記錄。[/yellow]")
        return

    table = Table(title=f"搜尋結果：{query}")
    table.add_column("時間", style="cyan", width=20)
    table.add_column("類型", style="yellow", width=8)
    table.add_column("輸入摘要", style="white")
    table.add_column("輸出", style="green")

    for r in results[-10:]:
        ts = r.get("timestamp", "—")[:19]
        dt = r.get("doc_type", "—")
        inp = r.get("input", "—")[:30]
        out = r.get("output", "—")
        table.add_row(ts, dt, inp, out)

    console.print(table)
    console.print(f"\n[dim]共找到 {len(results)} 筆符合的記錄。[/dim]")


@app.command(name="clear")
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

    original_count = len(records)
    remaining = records

    if before:
        try:
            cutoff = datetime.strptime(before, "%Y-%m-%d")
            remaining = [
                r for r in remaining
                if datetime.fromisoformat(r.get("timestamp", "9999-12-31")[:10]) >= cutoff
            ]
        except ValueError:
            console.print("[red]錯誤：日期格式無效，請使用 YYYY-MM-DD。[/red]")
            raise typer.Exit(1)
    elif keep > 0:
        remaining = remaining[-keep:]
    else:
        remaining = []

    deleted_count = original_count - len(remaining)

    if deleted_count == 0:
        console.print("[yellow]沒有符合條件的記錄需要清除。[/yellow]")
        return

    if not yes:
        console.print(f"[yellow]即將刪除 {deleted_count} 筆記錄（共 {original_count} 筆）。[/yellow]")
        console.print("[dim]使用 --yes 跳過確認。[/dim]")
        raise typer.Exit(0)

    _history_store.save(remaining)

    console.print(f"[green]已清除 {deleted_count} 筆記錄，保留 {len(remaining)} 筆。[/green]")


@app.command(name="filter")
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
        results = [r for r in results if r.get("doc_type") == doc_type]
    if score_min > 0:
        results = [r for r in results if float(r.get("score", 0)) >= score_min]
    if after:
        try:
            cutoff = datetime.strptime(after, "%Y-%m-%d")
            results = [r for r in results if datetime.fromisoformat(r.get("timestamp", "")[:10]) >= cutoff]
        except ValueError:
            console.print("[red]日期格式錯誤，請使用 YYYY-MM-DD。[/red]")
            raise typer.Exit(1)
    if before:
        try:
            cutoff = datetime.strptime(before, "%Y-%m-%d")
            results = [r for r in results if datetime.fromisoformat(r.get("timestamp", "")[:10]) <= cutoff]
        except ValueError:
            console.print("[red]日期格式錯誤。[/red]")
            raise typer.Exit(1)

    if not results:
        console.print("[yellow]沒有符合條件的記錄。[/yellow]")
        return

    table = Table(title="篩選結果")
    table.add_column("時間", style="cyan", width=20)
    table.add_column("類型", style="yellow", width=8)
    table.add_column("輸入", style="white")
    table.add_column("分數", style="green", justify="right")
    for r in results[-20:]:
        table.add_row(
            r.get("timestamp", "")[:19],
            r.get("doc_type", ""),
            r.get("input", "")[:30],
            str(r.get("score", "")),
        )
    console.print(table)
    console.print(f"\n[dim]共 {len(results)} 筆符合條件。[/dim]")


_TAGS_FILE = os.path.join(".history", "tags.json")


def _get_state_file_path(relative_path: str, *, for_write: bool) -> str:
    if not for_write:
        return resolve_state_read_path(relative_path)
    read_path = resolve_state_read_path(relative_path)
    write_path = resolve_state_path(relative_path)
    if read_path != write_path and os.path.isfile(read_path) and not os.path.exists(write_path):
        return read_path
    return write_path


def _get_history_dir_path(*, for_write: bool) -> str:
    if not for_write:
        return resolve_state_read_path(".history")
    read_path = resolve_state_read_path(".history")
    write_path = resolve_state_path(".history")
    if read_path != write_path and os.path.isdir(read_path) and not os.path.exists(write_path):
        return read_path
    return write_path


def _get_tags_path(*, for_write: bool = False) -> str:
    return _get_state_file_path(_TAGS_FILE, for_write=for_write)


def _load_tags() -> dict[str, list[str]]:
    path = _get_tags_path()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_tags(tags: dict[str, list[str]]) -> None:
    atomic_json_write(_get_tags_path(for_write=True), tags)


@app.command(name="tag-add")
def tag_add(
    record_id: str = typer.Argument(..., help="記錄 ID"),
    tag: str = typer.Argument(..., help="標籤名稱"),
) -> None:
    """為指定記錄加入標籤。"""
    tags = _load_tags()
    if record_id not in tags:
        tags[record_id] = []
    if tag not in tags[record_id]:
        tags[record_id].append(tag)
    _save_tags(tags)
    console.print(f"[green]已加入標籤「{tag}」至記錄 {record_id}。[/green]")


@app.command(name="tag-remove")
def tag_remove(
    record_id: str = typer.Argument(..., help="記錄 ID"),
    tag: str = typer.Argument(..., help="標籤名稱"),
) -> None:
    """移除指定記錄的標籤。"""
    tags = _load_tags()
    if record_id in tags and tag in tags[record_id]:
        tags[record_id].remove(tag)
        if not tags[record_id]:
            del tags[record_id]
        _save_tags(tags)
        console.print(f"[green]已移除記錄 {record_id} 的標籤「{tag}」。[/green]")
    else:
        console.print(f"[yellow]未找到標籤「{tag}」於記錄 {record_id}。[/yellow]")


@app.command(name="tag-list")
def tag_list(
    record_id: str = typer.Option("", help="查詢特定記錄的標籤"),
) -> None:
    """列出標籤。"""
    tags = _load_tags()
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
        for t in record_tags:
            table.add_row(t)
        console.print(table)
    else:
        table = Table(title="所有標籤")
        table.add_column("記錄 ID", style="cyan")
        table.add_column("標籤", style="green")
        for rid, tag_list_val in tags.items():
            table.add_row(rid, ", ".join(tag_list_val))
        console.print(table)


@app.command(name="duplicate")
def duplicate(
    threshold: float = typer.Option(0.8, "--threshold", "-t", help="相似度門檻（0.0-1.0）"),
) -> None:
    """偵測可能重複的歷史記錄。"""
    history_dir = _get_history_dir_path(for_write=False)
    if not os.path.isdir(history_dir):
        console.print("[yellow]找不到歷史記錄。[/yellow]")
        return

    # 讀取所有 .json 記錄檔（排除 tags.json）
    records: list[tuple[str, str]] = []
    for fname in sorted(os.listdir(history_dir)):
        if not fname.endswith(".json") or fname == "tags.json":
            continue
        fpath = os.path.join(history_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            subject = data.get("subject", "")
            if subject:
                records.append((fname, subject))
        except (json.JSONDecodeError, OSError):
            continue

    if len(records) < 2:
        console.print("[green]未發現重複記錄。[/green]")
        return

    # 兩兩比對主旨相似度
    duplicates: list[tuple[str, str, str, str, float]] = []
    for (fname_a, subj_a), (fname_b, subj_b) in combinations(records, 2):
        ratio = difflib.SequenceMatcher(None, subj_a, subj_b).ratio()
        if ratio >= threshold:
            duplicates.append((fname_a, subj_a, fname_b, subj_b, ratio))

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
    for fname_a, subj_a, fname_b, subj_b, ratio in duplicates:
        table.add_row(fname_a, subj_a, fname_b, subj_b, f"{ratio:.2f}")
    console.print(table)


@app.command(name="rename")
def rename(
    record_id: str = typer.Argument(..., help="記錄 ID"),
    new_name: str = typer.Argument(..., help="新的備註/主旨"),
) -> None:
    """重新命名指定記錄的主旨。"""
    history_dir = _get_history_dir_path(for_write=True)
    if not os.path.isdir(history_dir):
        console.print("[red]找不到歷史記錄目錄。[/red]")
        raise typer.Exit(1)

    record_path = os.path.join(history_dir, f"{record_id}.json")
    if not os.path.isfile(record_path):
        console.print(f"[red]找不到記錄 {record_id}。[/red]")
        raise typer.Exit(1)

    try:
        with open(record_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        console.print("[red]記錄檔案損壞。[/red]")
        raise typer.Exit(1)

    data["subject"] = new_name

    atomic_json_write(record_path, data)

    console.print(f"[green]已重命名記錄 {record_id} 的主旨為「{new_name}」。[/green]")


_PINS_FILE = os.path.join(".history", "pins.json")


def _get_pins_path(*, for_write: bool = False) -> str:
    return _get_state_file_path(_PINS_FILE, for_write=for_write)


def _load_pins() -> list[str]:
    path = _get_pins_path()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_pins(pins: list[str]) -> None:
    atomic_json_write(_get_pins_path(for_write=True), pins)


@app.command(name="pin")
def pin(
    record_id: str = typer.Argument(..., help="記錄 ID"),
) -> None:
    """釘選指定的歷史記錄。"""
    pins = _load_pins()
    if record_id in pins:
        console.print(f"[yellow]記錄 {record_id} 已經是釘選狀態。[/yellow]")
        return
    pins.append(record_id)
    _save_pins(pins)
    console.print(f"[green]已釘選記錄 {record_id}。[/green]")


@app.command(name="unpin")
def unpin(
    record_id: str = typer.Argument(..., help="記錄 ID"),
) -> None:
    """取消釘選指定的歷史記錄。"""
    pins = _load_pins()
    if record_id not in pins:
        console.print(f"[yellow]記錄 {record_id} 未釘選。[/yellow]")
        return
    pins.remove(record_id)
    _save_pins(pins)
    console.print(f"[green]已取消釘選記錄 {record_id}。[/green]")


_ARCHIVE_EXCLUDE = {"tags.json", "pins.json"}


@app.command(name="archive")
def history_archive(
    days: int = typer.Option(30, "--days", "-d", help="封存超過 N 天的記錄"),
    yes: bool = typer.Option(False, "--yes", "-y", help="跳過確認"),
) -> None:
    """封存超過指定天數的歷史記錄。"""
    history_dir = _get_history_dir_path(for_write=True)
    if not os.path.isdir(history_dir):
        console.print("[yellow]找不到歷史記錄[/yellow]")
        return

    now = time.time()
    cutoff = now - days * 86400
    old_files: list[str] = []

    for fname in os.listdir(history_dir):
        if not fname.endswith(".json") or fname in _ARCHIVE_EXCLUDE:
            continue
        fpath = os.path.join(history_dir, fname)
        if not os.path.isfile(fpath):
            continue
        if os.path.getmtime(fpath) < cutoff:
            old_files.append(fname)

    if not old_files:
        console.print("[green]無需封存[/green]")
        return

    if not yes:
        console.print(f"[yellow]找到 {len(old_files)} 筆可封存記錄[/yellow]")
        console.print("[dim]使用 --yes 確認封存。[/dim]")
        return

    archive_dir = os.path.join(history_dir, "archive")
    os.makedirs(archive_dir, exist_ok=True)

    for fname in old_files:
        src = os.path.join(history_dir, fname)
        dst = os.path.join(archive_dir, fname)
        shutil.move(src, dst)

    console.print(f"[green]已封存 {len(old_files)} 筆記錄[/green]")


@app.command(name="compare")
def history_compare(
    id_a: str = typer.Argument(..., help="第一筆記錄 ID"),
    id_b: str = typer.Argument(..., help="第二筆記錄 ID"),
) -> None:
    """比較兩筆歷史記錄的差異。"""
    history_dir = _get_history_dir_path(for_write=False)
    if not os.path.isdir(history_dir):
        console.print("[red]找不到歷史記錄目錄。[/red]")
        raise typer.Exit(1)

    path_a = os.path.join(history_dir, f"{id_a}.json")
    path_b = os.path.join(history_dir, f"{id_b}.json")

    for label, path in [("A", path_a), ("B", path_b)]:
        if not os.path.isfile(path):
            console.print(f"[red]找不到記錄 {label}：{path}[/red]")
            raise typer.Exit(1)

    with open(path_a, "r", encoding="utf-8") as f:
        rec_a = json.load(f)
    with open(path_b, "r", encoding="utf-8") as f:
        rec_b = json.load(f)

    table = Table(title=f"比較：{id_a} vs {id_b}")
    table.add_column("欄位", style="cyan")
    table.add_column(id_a, style="green")
    table.add_column(id_b, style="yellow")

    compare_fields = ["subject", "doc_type", "score", "risk", "timestamp"]
    for field in compare_fields:
        val_a = str(rec_a.get(field, "—"))
        val_b = str(rec_b.get(field, "—"))
        style_a = "[red]" if val_a != val_b else ""
        style_b = "[red]" if val_a != val_b else ""
        table.add_row(field, f"{style_a}{val_a}", f"{style_b}{val_b}")

    console.print(table)
