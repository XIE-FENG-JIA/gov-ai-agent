import os
import typer
from rich.console import Console
from rich.table import Table

console = Console()

def _calc_depth(filepath: str, base: str) -> int:
    """計算檔案相對於 base 目錄的巢狀層級深度（直接子檔=1）。"""
    try:
        rel = os.path.relpath(filepath, base)
    except ValueError:
        rel = os.path.basename(filepath)
    parts = os.path.normpath(rel).replace("\\", "/").split("/")
    return len(parts)


def toc(
    files: list[str] = typer.Argument(..., help="公文檔案路徑"),
    output: str = typer.Option("", "-o", "--output", help="匯出目錄為 Markdown 檔案"),
    depth: int = typer.Option(3, "--depth", "-d", help="目錄最大層級深度（1-5）"),
    fmt: str = typer.Option("table", "--format", "-f", help="輸出格式（table/list/csv）"),
):
    """生成公文目錄摘要。"""
    # 限制 depth 為 1-5 的範圍
    depth = max(1, min(5, depth))

    if not files:
        console.print("[red]錯誤：請指定至少一個檔案。[/red]")
        raise typer.Exit(1)

    # 計算所有檔案的共同父目錄作為深度基準
    abs_files = [os.path.abspath(f) for f in files]
    base_dir = os.path.commonpath([os.path.dirname(af) for af in abs_files]) if abs_files else os.getcwd()

    entries = []
    for i, f in enumerate(files, 1):
        file_depth = _calc_depth(os.path.abspath(f), base_dir)

        if not os.path.isfile(f):
            entries.append({"no": i, "file": f, "subject": "（找不到檔案）", "type": "—", "depth": file_depth})
            continue
        try:
            with open(f, "r", encoding="utf-8-sig") as fh:
                text = fh.read()
        except UnicodeDecodeError:
            entries.append({
                "no": i, "file": os.path.basename(f),
                "subject": "（編碼錯誤）", "type": "—",
                "depth": file_depth,
            })
            continue

        subject = "（無主旨）"
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("主旨"):
                subject = stripped[len("主旨"):].lstrip("：:").strip()[:40]
                break

        doc_type = "—"
        type_keywords = {"函": "函", "公告": "公告", "簽": "簽", "書函": "書函", "令": "令", "呈": "呈"}
        for kw, dt in type_keywords.items():
            if kw in text[:100]:
                doc_type = dt
                break

        entries.append({
            "no": i, "file": os.path.basename(f),
            "subject": subject, "type": doc_type,
            "depth": file_depth,
        })

    # 只顯示層級 <= depth 的檔案
    filtered = [e for e in entries if e["depth"] <= depth]

    fmt_val = fmt.lower().strip()
    if fmt_val == "csv":
        import csv
        import io
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["序號", "檔案", "主旨", "類型", "層級"])
        for e in filtered:
            writer.writerow([e["no"], e["file"], e["subject"], e["type"], e["depth"]])
        console.print(buf.getvalue())
        console.print("\n[dim]格式：CSV[/dim]")
    elif fmt_val == "list":
        for e in filtered:
            console.print(f"  {e['no']}. {e['file']} — {e['subject']}（{e['type']}）")
        console.print("\n[dim]格式：清單[/dim]")
    elif fmt_val == "table":
        table = Table(title="公文目錄")
        table.add_column("序號", style="cyan", justify="right", width=6)
        table.add_column("檔案", style="green")
        table.add_column("主旨", style="white")
        table.add_column("類型", style="yellow", width=8)
        table.add_column("層級", style="magenta", justify="right", width=6)
        for e in filtered:
            table.add_row(str(e["no"]), e["file"], e["subject"], e["type"], str(e["depth"]))
        console.print(table)
    else:
        console.print(f"[yellow]未知的格式：{fmt}（可用：table/list/csv）[/yellow]")
        table = Table(title="公文目錄")
        table.add_column("序號", style="cyan", justify="right", width=6)
        table.add_column("檔案", style="green")
        table.add_column("主旨", style="white")
        table.add_column("類型", style="yellow", width=8)
        table.add_column("層級", style="magenta", justify="right", width=6)
        for e in filtered:
            table.add_row(str(e["no"]), e["file"], e["subject"], e["type"], str(e["depth"]))
        console.print(table)

    console.print(f"\n[dim]共 {len(filtered)} 份公文。[/dim]")
    console.print(f"  [dim]顯示深度：{depth} 層[/dim]")

    if output:
        lines = ["# 公文目錄\n"]
        for e in filtered:
            lines.append(f"{e['no']}. **{e['file']}** — {e['subject']}（{e['type']}）")
        with open(output, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        console.print(f"[green]已匯出目錄至：{output}[/green]")
