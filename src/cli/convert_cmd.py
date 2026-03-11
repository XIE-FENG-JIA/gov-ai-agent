"""公文格式轉換指令。

將 .docx 公文轉換為 Markdown 或純文字格式。
"""
import os
import typer
from rich.console import Console

console = Console()


def convert(
    input_file: str = typer.Argument(..., help="輸入的 .docx 檔案路徑"),
    format: str = typer.Option("md", "--format", help="輸出格式（md 或 txt）"),
    output: str = typer.Option("", "--output", "-o", help="輸出檔案路徑（預設同名）"),
    encoding: str = typer.Option("utf-8", "--encoding", "-e", help="輸出編碼（utf-8/big5/utf-8-sig）"),
):
    """將 .docx 公文轉換為 Markdown 或純文字格式。"""
    if not os.path.exists(input_file):
        console.print(f"[red]錯誤：找不到檔案「{input_file}」。[/red]")
        raise typer.Exit(1)

    if not input_file.lower().endswith(".docx"):
        console.print("[red]錯誤：僅支援 .docx 格式的檔案。[/red]")
        raise typer.Exit(1)

    if format not in ("md", "txt"):
        console.print(f"[red]錯誤：不支援的輸出格式「{format}」，請使用 md 或 txt。[/red]")
        raise typer.Exit(1)

    from docx import Document

    doc = Document(input_file)
    paragraphs = [p.text for p in doc.paragraphs]

    if format == "md":
        content = "\n\n".join(paragraphs)
    else:
        content = "\n".join(paragraphs)

    if output:
        out_path = output
    else:
        base = os.path.splitext(input_file)[0]
        out_path = f"{base}.{format}"

    _VALID_ENCODINGS = {"utf-8", "big5", "utf-8-sig"}
    enc = encoding.lower().strip() if encoding else "utf-8"
    if enc not in _VALID_ENCODINGS:
        console.print(f"[yellow]不支援的編碼 '{encoding}'，使用 utf-8。[/yellow]")
        enc = "utf-8"

    with open(out_path, "w", encoding=enc) as f:
        f.write(content)

    char_count = sum(len(p) for p in paragraphs)
    console.print(f"[green]轉換完成：{out_path}[/green]")
    console.print(f"[dim]共 {len(paragraphs)} 段落，{char_count} 字。[/dim]")
