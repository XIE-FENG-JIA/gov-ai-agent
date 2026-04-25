"""公文發文前檢核清單指令。

檢核公文是否包含所有必要欄位，確認可發文。
"""
import os
import re
import typer
from rich.console import Console

console = Console()


def checklist(
    file: str = typer.Argument(..., help="公文檔案路徑（.docx、.md 或 .txt）"),
    custom: str = typer.Option("", "--custom", help="額外檢核項目（逗號分隔，如 --custom '附件,聯絡人'）"),
):
    """
    檢核公文是否包含所有必要欄位，確認可發文。

    支援 .docx、.md、.txt 格式。

    範例：

        gov-ai checklist output.docx

        gov-ai checklist draft.txt
    """
    if not os.path.isfile(file):
        console.print(f"[red]錯誤：找不到檔案 {file}[/red]")
        raise typer.Exit(1)

    # 讀取檔案內容
    ext = os.path.splitext(file)[1].lower()
    if ext == ".docx":
        try:
            from docx import Document
            from docx.opc.exceptions import PackageNotFoundError
            from zipfile import BadZipFile
        except ImportError:
            console.print("[red]錯誤：需要 python-docx 套件。[/red]")
            raise typer.Exit(1)
        try:
            doc = Document(file)
            content = "\n".join(p.text for p in doc.paragraphs)
        except (OSError, ValueError, PackageNotFoundError, BadZipFile) as e:
            console.print(f"[red]無法開啟文件：{e}[/red]")
            raise typer.Exit(1)
    elif ext in (".md", ".txt"):
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        console.print(f"[red]錯誤：不支援的檔案格式 {ext}，僅支援 .docx、.md、.txt[/red]")
        raise typer.Exit(1)

    console.print(f"[bold cyan]正在檢核：{file}[/bold cyan]\n")

    # 檢核項目
    checks = [
        ("主旨", bool(re.search(r"主旨", content))),
        ("受文者", bool(re.search(r"受文者", content))),
        (
            "發文日期",
            bool(re.search(r"發文日期", content) or re.search(r"中華民國.*年.*月.*日", content)),
        ),
        (
            "發文字號",
            bool(re.search(r"發文字號", content) or re.search(r"字第.*號", content)),
        ),
        (
            "署名",
            bool(re.search(r"局長|處長|科長|主任", content)),
        ),
        ("正本/副本", bool(re.search(r"正本|副本", content))),
    ]

    # 自訂檢核項目
    if custom:
        custom_items = [item.strip() for item in custom.split(",") if item.strip()]
        for item in custom_items:
            checks.append((item, bool(re.search(re.escape(item), content))))

    # 輸出結果
    all_pass = True
    for name, ok in checks:
        if ok:
            console.print(f"  [green]✓[/green] {name}")
        else:
            console.print(f"  [red]✗[/red] {name}")
            all_pass = False

    console.print()
    if all_pass:
        console.print("[bold green]檢核通過，可發文。[/bold green]")
    else:
        console.print("[bold red]檢核未通過，請補充缺少項目。[/bold red]")
        raise typer.Exit(1)
