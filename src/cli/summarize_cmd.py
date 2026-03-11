from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()


def summarize(
    file_path: str = typer.Argument(..., help="公文檔案路徑"),
    max_length: int = typer.Option(100, "--max-length", "-m", help="摘要最大字數"),
    output: str = typer.Option("", "--output", "-o", help="匯出摘要至檔案"),
):
    """摘要公文內容，擷取主旨與說明。"""
    path = Path(file_path)
    if not path.exists():
        console.print("[red]錯誤：找不到檔案[/red]")
        raise typer.Exit(1)

    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # 擷取主旨
    title = ""
    for line in lines:
        if line.startswith("主旨：") or line.startswith("主旨:"):
            sep = "：" if "：" in line else ":"
            title = line.split(sep, 1)[1].strip()
            break

    # 擷取說明後的內容
    summary_body = ""
    found = False
    for line in lines:
        if found:
            summary_body += line
        elif line.startswith("說明：") or line.startswith("說明:"):
            sep = "：" if "：" in line else ":"
            rest = line.split(sep, 1)[1].strip()
            summary_body = rest
            found = True

    summary_body = summary_body[:max_length]

    # 組合摘要
    parts = []
    if title:
        parts.append(f"[bold]主旨：[/bold]{title}")
    if summary_body:
        parts.append(f"[bold]說明：[/bold]{summary_body}")

    display = "\n".join(parts) if parts else content[:max_length]
    console.print(Panel(display, title="摘要", border_style="blue"))

    if output:
        out_parts = []
        if title:
            out_parts.append(f"主旨：{title}")
        if summary_body:
            out_parts.append(f"說明：{summary_body}")
        out_text = "\n".join(out_parts) if out_parts else content[:max_length]
        Path(output).write_text(out_text, encoding="utf-8")
        console.print(f"[green]已匯出摘要至：{output}[/green]")
