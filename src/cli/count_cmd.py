import json
import os
import re
import typer
from rich.console import Console
from rich.table import Table

console = Console()

_SECTION_NAMES = ["主旨", "說明", "辦法", "擬辦", "正本", "副本", "備註", "附件"]


def count(
    file: str = typer.Option(..., "-f", "--file", help="要統計的公文檔案路徑"),
    exclude: str = typer.Option("", "--exclude", "-e", help="排除的段落（逗號分隔，如 --exclude '正本,副本'）"),
    output_json: bool = typer.Option(False, "--json", help="以 JSON 格式輸出"),
    exclude_punct: bool = typer.Option(False, "--exclude-punct", help="排除標點符號計數"),
):
    """統計公文的字數、行數與段落資訊。"""
    if not os.path.isfile(file):
        console.print(f"[red]錯誤：找不到檔案：{file}[/red]")
        raise typer.Exit(1)

    try:
        with open(file, "r", encoding="utf-8-sig") as f:
            text = f.read()
    except UnicodeDecodeError:
        console.print("[red]錯誤：檔案編碼不支援，請使用 UTF-8。[/red]")
        raise typer.Exit(1)

    lines = text.split("\n")
    raw_text = text.replace("\n", "").replace(" ", "")
    if exclude_punct:
        raw_text = re.sub(r'[，。、；：「」『』（）【】？！—…《》〈〉,.;:!?\-\[\](){}\'\"]+', '', raw_text)
    total_chars = len(raw_text)
    total_lines = len(lines)

    # 解析段落
    sections = {}
    current = None
    for line in lines:
        stripped = line.strip()
        matched = None
        for s in _SECTION_NAMES:
            if stripped.startswith(s):
                matched = s
                break
        if matched:
            current = matched
            after = stripped[len(matched):].lstrip("：:").strip()
            sections[current] = sections.get(current, "") + after
        elif current and stripped:
            sections[current] = sections[current] + stripped

    # 排除指定段落
    excluded = []
    if exclude:
        excluded = [s.strip() for s in exclude.split(",") if s.strip()]
        sections = {k: v for k, v in sections.items() if k not in excluded}

    stats = {
        "total_chars": total_chars,
        "total_lines": total_lines,
        "sections": len(sections),
        "section_details": {k: len(v) for k, v in sections.items()},
    }

    if output_json:
        console.print(json.dumps(stats, ensure_ascii=False, indent=2))
        return

    # Rich 表格輸出
    table = Table(title="公文統計")
    table.add_column("項目", style="cyan")
    table.add_column("數值", style="green", justify="right")

    table.add_row("總字數", f"{total_chars:,}")
    table.add_row("總行數", str(total_lines))
    table.add_row("段落數", str(len(sections)))

    console.print(table)

    if exclude_punct:
        console.print("  [dim]已排除標點符號[/dim]")

    if excluded:
        console.print(f"  [dim]已排除段落：{', '.join(excluded)}[/dim]")

    if sections:
        detail_table = Table(title="各段落字數")
        detail_table.add_column("段落", style="cyan")
        detail_table.add_column("字數", style="green", justify="right")
        for name, content in sections.items():
            detail_table.add_row(name, str(len(content)))
        console.print(detail_table)
