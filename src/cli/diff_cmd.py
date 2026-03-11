"""公文版本差異對照指令。

讀取兩份公文檔案，以 unified diff 格式呈現差異，並用 Rich 彩色標示。
"""
import difflib
from pathlib import Path

import typer
from rich.console import Console
from rich.text import Text

console = Console()


def diff(
    file_a: str = typer.Argument(..., help="第一份公文檔案路徑"),
    file_b: str = typer.Argument(..., help="第二份公文檔案路徑"),
    context_lines: int = typer.Option(3, "--context", "-c", help="顯示差異前後的上下文行數"),
    output: str = typer.Option("", "--output", "-o", help="匯出差異結果至檔案"),
):
    """
    比較兩份公文檔案的差異。

    支援 .txt 與 .md 檔案，以顏色標示新增（綠色）與刪除（紅色）的行。

    範例：

        gov-ai diff draft_v1.txt draft_v2.txt

        gov-ai diff old.md new.md -c 5
    """
    path_a = Path(file_a)
    path_b = Path(file_b)

    # 檢查檔案是否存在
    for p in (path_a, path_b):
        if not p.exists():
            console.print(f"[red]錯誤：找不到檔案「{p}」。[/red]")
            raise typer.Exit(1)

    lines_a = path_a.read_text(encoding="utf-8").splitlines(keepends=True)
    lines_b = path_b.read_text(encoding="utf-8").splitlines(keepends=True)

    diff_lines = list(
        difflib.unified_diff(
            lines_a, lines_b,
            fromfile=str(path_a), tofile=str(path_b),
            n=context_lines,
        )
    )

    if not diff_lines:
        console.print("[bold green]兩份文件內容相同。[/bold green]")
        return

    text_output = Text()
    for line in diff_lines:
        stripped = line.rstrip("\n")
        if line.startswith("+++") or line.startswith("---"):
            text_output.append(stripped + "\n", style="bold")
        elif line.startswith("@@"):
            text_output.append(stripped + "\n", style="cyan")
        elif line.startswith("+"):
            text_output.append(stripped + "\n", style="green")
        elif line.startswith("-"):
            text_output.append(stripped + "\n", style="red")
        else:
            text_output.append(stripped + "\n")

    console.print(text_output)

    if output:
        plain = "".join(line.rstrip("\n") + "\n" for line in diff_lines)
        Path(output).write_text(plain, encoding="utf-8")
        console.print(f"[green]已匯出差異至：{output}[/green]")
