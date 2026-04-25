import os
import typer
from rich.console import Console
from rich.table import Table

from src.cli.utils_io import atomic_text_write

console = Console()

_SECTION_NAMES = ["主旨", "說明", "辦法", "擬辦", "正本", "副本", "備註", "附件"]


def split(
    file: str = typer.Option(..., "-f", "--file", help="要拆分的公文檔案路徑"),
    output_dir: str = typer.Option("split_output", "-d", "--dir", help="輸出目錄"),
    by_section: bool = typer.Option(False, "--by-section", help="依公文段落（主旨/說明/辦法等）分割"),
    prefix: str = typer.Option("part", "--prefix", help="分割後檔名前綴（預設：part）"),
):
    """將公文依段落拆分為獨立檔案。"""
    if not os.path.isfile(file):
        console.print(f"[red]錯誤：找不到檔案：{file}[/red]")
        raise typer.Exit(1)

    try:
        with open(file, "r", encoding="utf-8-sig") as f:
            text = f.read()
    except UnicodeDecodeError:
        console.print("[red]錯誤：檔案編碼不支援。[/red]")
        raise typer.Exit(1)
    except OSError as e:
        console.print(f"[red]錯誤：無法讀取檔案：{file}（{e}）[/red]")
        raise typer.Exit(1)

    # 解析段落
    sections = []
    current_name = None
    current_lines = []

    for line in text.split("\n"):
        stripped = line.strip()
        matched = None
        for s in _SECTION_NAMES:
            if stripped.startswith(s):
                matched = s
                break
        if matched:
            if current_name:
                sections.append((current_name, "\n".join(current_lines)))
            current_name = matched
            after = stripped[len(matched):].lstrip("：:")
            current_lines = [after] if after.strip() else []
        elif current_name:
            current_lines.append(line)
        elif stripped:
            sections.append(("未分類", stripped))

    if current_name:
        sections.append((current_name, "\n".join(current_lines)))

    if not sections:
        console.print("[yellow]無法辨識任何段落結構。[/yellow]")
        raise typer.Exit(1)

    # 建立輸出目錄
    os.makedirs(output_dir, exist_ok=True)

    if by_section:
        console.print("  [dim]分割模式：段落分割[/dim]")
    else:
        console.print("  [dim]分割模式：一般分割[/dim]")

    table_title = "段落分割結果" if by_section else "拆分結果"
    table = Table(title=table_title)
    table.add_column("段落", style="cyan")
    table.add_column("檔案", style="green")
    table.add_column("字數", style="yellow", justify="right")

    for i, (name, content) in enumerate(sections, 1):
        fname = f"{prefix}_{i:02d}_{name}.txt"
        fpath = os.path.join(output_dir, fname)
        atomic_text_write(fpath, content.strip())
        table.add_row(name, fname, str(len(content.strip())))

    console.print(table)
    if prefix != "part":
        console.print(f"  [dim]檔名前綴：{prefix}[/dim]")
    console.print(f"\n[green]已拆分 {len(sections)} 個段落至 {output_dir}/[/green]")
