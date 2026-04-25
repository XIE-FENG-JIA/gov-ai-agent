from pathlib import Path

import typer
from rich.console import Console

from src.cli.utils_io import atomic_text_write

console = Console()

SECTION_KEYWORDS = ["主旨", "說明", "辦法", "正本", "副本"]


def _format_content(content: str, indent: int) -> str:
    """格式化公文內容：關鍵字冒號後加空格，段落內容加縮排。"""
    lines = content.splitlines()
    result: list[str] = []
    indent_str = " " * indent

    for line in lines:
        matched = False
        for kw in SECTION_KEYWORDS:
            if line.startswith(kw):
                # 取得關鍵字後的部分
                rest = line[len(kw):]
                # 確保冒號後有空格
                if rest.startswith("："):
                    body = rest[1:].lstrip()
                    line = f"{kw}：{body}" if body else f"{kw}："
                elif rest.startswith(":"):
                    body = rest[1:].lstrip()
                    line = f"{kw}：{body}" if body else f"{kw}："
                result.append(line)
                matched = True
                break
        if not matched:
            # 非關鍵字行加上縮排
            stripped = line.strip()
            if stripped:
                result.append(f"{indent_str}{stripped}")
            else:
                result.append("")

    return "\n".join(result)


def format_doc(
    file_path: str = typer.Argument(..., help="要格式化的公文檔案路徑（.txt/.md）"),
    indent: int = typer.Option(2, "--indent", help="段落縮排空格數"),
    in_place: bool = typer.Option(False, "--in-place", "-i", help="就地修改檔案"),
    check: bool = typer.Option(False, "--check", help="僅檢查是否需要格式化（不修改檔案）"),
):
    """格式化公文文件，統一關鍵字格式與段落縮排。"""
    path = Path(file_path)
    if not path.exists():
        console.print("[red]錯誤：找不到檔案[/red]")
        raise typer.Exit(1)

    content = path.read_text(encoding="utf-8")
    formatted = _format_content(content, indent)

    if check:
        if content == formatted:
            console.print(f"[green]✓ 格式正確，無需修改：{path}[/green]")
        else:
            console.print(f"[yellow]✗ 需要格式化：{path}[/yellow]")
            raise typer.Exit(1)
        return

    if in_place:
        atomic_text_write(str(path), formatted)
        console.print(f"[green]已格式化：{path}[/green]")
    else:
        console.print(formatted)
        console.print("\n[green]已格式化[/green]")
