import os
import re
from pathlib import Path

import typer
from rich.console import Console

from src.cli.utils_io import atomic_text_write

console = Console()

_PATTERNS = {
    "手機號碼": re.compile(r"09\d{2}[-]?\d{3}[-]?\d{3}"),
    "身分證字號": re.compile(r"[A-Z][12]\d{8}"),
    "Email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "地址門牌": re.compile(r"\d+巷\d+弄\d+號|\d+號\d+樓|\d+之\d+號"),
}
_MASK = "●●●"

def redact(
    file: str = typer.Option(..., "-f", "--file", help="要遮蔽的公文檔案路徑"),
    output: str = typer.Option("", "-o", "--output", help="遮蔽後的輸出檔案路徑"),
    pattern: str = typer.Option("", "--pattern", "-p", help="自訂遮蔽正則表達式"),
    mode: str = typer.Option("mask", "--mode", "-m", help="遮蔽模式（mask/remove/highlight）"),
):
    """遮蔽公文中的個人資料。"""
    if not os.path.isfile(file):
        console.print(f"[red]錯誤：找不到檔案：{file}[/red]")
        raise typer.Exit(1)

    if pattern:
        try:
            custom_regex = re.compile(pattern)
        except re.error:
            console.print(f"[red]錯誤：無效的正則表達式：{pattern}[/red]")
            raise typer.Exit(1)
    else:
        custom_regex = None

    try:
        with open(file, "r", encoding="utf-8-sig") as f:
            text = f.read()
    except UnicodeDecodeError:
        console.print("[red]錯誤：檔案編碼不支援。[/red]")
        raise typer.Exit(1)

    _MODE_MAP = {"mask": "●●●", "remove": "", "highlight": None}
    if mode.lower().strip() not in _MODE_MAP:
        console.print(f"[yellow]未知的遮蔽模式：{mode}（可用：mask/remove/highlight），使用預設 mask[/yellow]")
        mode = "mask"

    replacement = _MODE_MAP[mode.lower().strip()]

    total_redacted = 0
    stats = {}
    result_text = text
    for name, pat in _PATTERNS.items():
        matches = pat.findall(result_text)
        if matches:
            stats[name] = len(matches)
            total_redacted += len(matches)
            if mode.lower().strip() == "highlight":
                result_text = pat.sub(lambda m: f"[{m.group()}]", result_text)
            else:
                result_text = pat.sub(replacement, result_text)

    if custom_regex:
        matches = custom_regex.findall(result_text)
        if matches:
            stats["自訂規則"] = len(matches)
            total_redacted += len(matches)
            result_text = custom_regex.sub("[已遮蔽]", result_text)

    _MODE_LABELS = {"mask": "遮蔽替換", "remove": "直接移除", "highlight": "標記高亮"}
    mode_label = _MODE_LABELS.get(mode.lower().strip(), "遮蔽替換")
    console.print(f"  [dim]遮蔽模式：{mode_label}[/dim]")

    if total_redacted == 0:
        console.print("[green]未偵測到需要遮蔽的個資。[/green]")
        return

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(result_text)
        console.print(f"[green]已遮蔽 {total_redacted} 處個資，儲存至：{output}[/green]")
    else:
        console.print(result_text)
        console.print(f"\n[green]共遮蔽 {total_redacted} 處個資。[/green]")

    from rich.table import Table
    table = Table(title="遮蔽統計")
    table.add_column("類別", style="cyan")
    table.add_column("數量", style="yellow", justify="right")
    for name, count in stats.items():
        table.add_row(name, str(count))
    console.print(table)


def replace_text(
    file_path: str = typer.Argument(..., help="公文檔案路徑"),
    old: str = typer.Option(..., "--old", help="要替換的文字"),
    new: str = typer.Option(..., "--new", help="替換成的文字"),
    count: int = typer.Option(0, "--count", "-c", help="替換次數（0=全部）"),
    backup: bool = typer.Option(False, "--backup", "-b", help="替換前備份原始檔案"),
):
    """批量替換公文中的指定文字。"""
    path = Path(file_path)
    if not path.exists():
        console.print("[red]錯誤：找不到檔案[/red]")
        raise typer.Exit(1)

    content = path.read_text(encoding="utf-8")

    if old not in content:
        console.print(f"[yellow]未找到「{old}」[/yellow]")
        return

    if count == 0:
        replaced = content.replace(old, new)
        n = content.count(old)
    else:
        replaced = content.replace(old, new, count)
        n = min(count, content.count(old))

    if backup:
        import shutil
        backup_path = str(path) + ".bak"
        shutil.copy2(str(path), backup_path)
        console.print(f"[dim]已備份至：{backup_path}[/dim]")

    atomic_text_write(str(path), replaced)
    console.print(f"[green]已替換 {n} 處[/green]")
