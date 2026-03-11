"""草稿版本比較指令。

比較兩個公文草稿檔案的差異，以 Rich 彩色輸出顯示新增與刪除的內容。
"""
import difflib
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

_SUPPORTED_EXTENSIONS = {".md", ".txt"}


def compare(
    file_a: str = typer.Argument(..., help="第一個草稿檔案路徑"),
    file_b: str = typer.Argument(..., help="第二個草稿檔案路徑"),
    stats_only: bool = typer.Option(False, "--stats-only", help="僅顯示差異統計"),
):
    """
    比較兩個草稿版本的差異。

    支援 .md 與 .txt 檔案，以顏色標示新增（綠色）與刪除（紅色）的行。

    範例：

        gov-ai compare draft_v1.md draft_v2.md
    """
    path_a = Path(file_a)
    path_b = Path(file_b)

    # 檢查檔案是否存在
    for p in (path_a, path_b):
        if not p.exists():
            console.print(f"[red]錯誤：找不到檔案「{p}」。[/red]")
            raise typer.Exit(1)

    # 檢查副檔名
    for p in (path_a, path_b):
        if p.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            console.print(
                f"[red]錯誤：不支援的檔案格式「{p.suffix}」。僅支援 .md 與 .txt。[/red]"
            )
            raise typer.Exit(1)

    lines_a = path_a.read_text(encoding="utf-8").splitlines(keepends=True)
    lines_b = path_b.read_text(encoding="utf-8").splitlines(keepends=True)

    diff = list(
        difflib.unified_diff(lines_a, lines_b, fromfile=str(path_a), tofile=str(path_b))
    )

    if not diff:
        console.print(
            Panel(
                "[bold]兩個檔案內容完全相同，無差異。[/bold]",
                title="[bold cyan]比較結果[/bold cyan]",
                border_style="cyan",
            )
        )
        return

    # 統計差異
    added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))

    if stats_only:
        console.print("[bold]差異統計：[/bold]")
        console.print(f"  [green]+{added} 行新增[/green]")
        console.print(f"  [red]-{removed} 行刪除[/red]")
        console.print(f"  [dim]共 {added + removed} 處變更[/dim]")
        return

    # 顯示差異
    output = Text()
    for line in diff:
        stripped = line.rstrip("\n")
        if line.startswith("+++") or line.startswith("---"):
            output.append(stripped + "\n", style="bold")
        elif line.startswith("@@"):
            output.append(stripped + "\n", style="cyan")
        elif line.startswith("+"):
            output.append(stripped + "\n", style="green")
        elif line.startswith("-"):
            output.append(stripped + "\n", style="red")
        else:
            output.append(stripped + "\n")

    console.print(
        Panel(
            output,
            title="[bold cyan]草稿差異比較[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    # 顯示統計
    console.print(
        f"[dim]統計：[green]+{added} 行新增[/green]  [red]-{removed} 行刪除[/red][/dim]"
    )
