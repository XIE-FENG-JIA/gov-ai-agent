import os
from datetime import datetime

import typer
from rich.console import Console

console = Console()


def stamp(
    file_path: str = typer.Argument(..., help="要加蓋戳記的檔案路徑（.txt/.md）"),
    text: str = typer.Option("已核閱", "--text", "-t", help="戳記文字"),
    stamper: str = typer.Option("", "--stamper", "-s", help="戳記者姓名"),
    with_time: bool = typer.Option(True, "--with-time/--no-with-time", help="是否加時間戳記"),
    verify: bool = typer.Option(False, "--verify", help="驗證檔案是否已有戳記（不加蓋新戳記）"),
    position: str = typer.Option("bottom-right", "--position", help="戳記位置（top-right/bottom-right/bottom-center）"),
):
    """為公文檔案加蓋電子戳記。"""
    if not os.path.isfile(file_path):
        console.print(f"[red]錯誤：找不到檔案：{file_path}[/red]")
        raise typer.Exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    if verify:
        has_stamp = "[戳記]" in content
        if has_stamp:
            # 找出所有戳記行
            stamps = [line.strip() for line in content.split("\n") if "[戳記]" in line]
            console.print(f"[green]檔案已有 {len(stamps)} 個戳記：[/green]")
            for s in stamps:
                console.print(f"  {s}")
        else:
            console.print("[yellow]檔案尚未加蓋戳記。[/yellow]")
        return

    _POS_MAP = {"top-right": "右上角", "bottom-right": "右下角", "bottom-center": "下方置中"}
    pos_label = _POS_MAP.get(position.lower().strip(), "")
    if not pos_label:
        console.print(
            f"[yellow]未知的位置：{position}"
            "（可用：top-right/bottom-right/bottom-center），"
            "使用預設 bottom-right[/yellow]"
        )
        pos_label = "右下角"

    stamp_line = f"\n---\n[戳記] {text}"
    if pos_label:
        stamp_line += f" | 位置：{pos_label}"
    if stamper:
        stamp_line += f" | 戳記者：{stamper}"
    if with_time:
        stamp_line += f" | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    stamp_line += "\n"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content + stamp_line)

    console.print(f"[green]已成功加蓋戳記至：{file_path}[/green]")
    console.print(f"  [dim]戳記位置：{pos_label}[/dim]")
