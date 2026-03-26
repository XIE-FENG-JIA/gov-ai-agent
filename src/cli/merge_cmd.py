import os
import typer
from rich.console import Console
from rich.panel import Panel

from src.cli.utils import atomic_text_write

console = Console()


def merge(
    files: list[str] = typer.Argument(..., help="要合併的公文檔案路徑（至少 2 個）"),
    output: str = typer.Option("", "-o", "--output", help="合併結果輸出檔案路徑"),
):
    """合併多份公文片段為一份完整公文。"""
    if len(files) < 2:
        console.print("[red]錯誤：至少需要 2 個檔案才能合併。[/red]")
        raise typer.Exit(1)

    # 驗證檔案存在
    for f in files:
        if not os.path.isfile(f):
            console.print(f"[red]錯誤：找不到檔案：{f}[/red]")
            raise typer.Exit(1)

    # 讀取各檔案
    contents = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8-sig") as fh:
                contents.append(fh.read().strip())
        except UnicodeDecodeError:
            console.print(f"[red]錯誤：檔案編碼不支援：{f}[/red]")
            raise typer.Exit(1)
        except OSError as e:
            console.print(f"[red]錯誤：無法讀取檔案：{f}（{e}）[/red]")
            raise typer.Exit(1)

    # 智慧合併
    merged = _smart_merge(contents)

    # 顯示預覽
    console.print(Panel(merged, title="[bold cyan]合併結果預覽[/bold cyan]", border_style="cyan"))
    console.print(f"\n[green]已合併 {len(files)} 個檔案。[/green]")

    # 輸出到檔案
    if output:
        atomic_text_write(output, merged)
        console.print(f"[green]已儲存至：{output}[/green]")


def _smart_merge(contents: list[str]) -> str:
    """智慧合併多份公文內容。"""
    sections = {}  # section_name -> list of content lines
    other_lines = []

    _SECTION_NAMES = ["主旨", "說明", "辦法", "擬辦", "正本", "副本", "備註"]

    for content in contents:
        current_section = None
        for line in content.split("\n"):
            stripped = line.strip()
            # 檢查是否為段落標題行
            matched_section = None
            for s in _SECTION_NAMES:
                if stripped.startswith(s):
                    matched_section = s
                    break

            if matched_section:
                current_section = matched_section
                if current_section not in sections:
                    sections[current_section] = []
                # 提取標題後的內容
                after_title = stripped[len(matched_section):].lstrip("：:").strip()
                if after_title:
                    sections[current_section].append(after_title)
            elif current_section:
                if stripped:
                    sections[current_section].append(stripped)
            else:
                if stripped:
                    other_lines.append(stripped)

    # 組裝結果
    result_parts = []
    for s in _SECTION_NAMES:
        if s in sections and sections[s]:
            items = sections[s]
            if len(items) == 1:
                result_parts.append(f"{s}：{items[0]}")
            else:
                result_parts.append(f"{s}：")
                for idx, item in enumerate(items, 1):
                    result_parts.append(f"  {idx}. {item}")

    if other_lines:
        result_parts.extend(other_lines)

    return "\n".join(result_parts) if result_parts else "\n\n---\n\n".join(contents)
