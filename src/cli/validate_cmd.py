"""公文驗證指令。

驗證現有公文 .docx 檔案是否符合格式規範。
"""
import os
import typer
from rich.console import Console
from rich.table import Table

console = Console()


def validate(
    file_path: str = typer.Argument(..., help="要驗證的 .docx 檔案路徑"),
):
    """
    驗證現有公文 .docx 檔案是否符合格式規範。

    檢查項目包含：文件結構、必要欄位、格式一致性。

    範例：

        gov-ai validate output.docx
    """
    if not os.path.isfile(file_path):
        console.print(f"[red]錯誤：找不到檔案 {file_path}[/red]")
        raise typer.Exit(1)

    if not file_path.endswith(".docx"):
        console.print("[red]錯誤：僅支援 .docx 檔案格式。[/red]")
        raise typer.Exit(1)

    try:
        from docx import Document
    except ImportError:
        console.print("[red]錯誤：需要 python-docx 套件。[/red]")
        raise typer.Exit(1)

    console.print(f"[bold cyan]正在驗證：{file_path}[/bold cyan]\n")

    checks: list[tuple[str, bool, str]] = []

    try:
        from docx.opc.exceptions import PackageNotFoundError
        from zipfile import BadZipFile
        doc = Document(file_path)
    except (OSError, ValueError, PackageNotFoundError, BadZipFile) as e:
        console.print(f"[red]無法開啟文件：{e}[/red]")
        raise typer.Exit(1)

    # 1. 基本結構檢查
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    if len(paragraphs) < 3:
        checks.append(("文件長度", False, f"僅 {len(paragraphs)} 段，內容可能不完整"))
    else:
        checks.append(("文件長度", True, f"{len(paragraphs)} 段"))

    # 2. 公文類型識別
    known_types = {
        "函", "公告", "簽", "書函", "令", "開會通知單",
        "呈", "咨", "會勘通知單", "公務電話紀錄", "手令", "箋函",
    }
    full_text = "\n".join(paragraphs)
    found_type = None
    for dt in known_types:
        if dt in full_text[:200]:
            found_type = dt
            break
    if found_type:
        checks.append(("公文類型", True, f"識別為「{found_type}」"))
    else:
        checks.append(("公文類型", False, "無法識別公文類型"))

    # 3. 必要欄位檢查
    required_fields = ["主旨", "說明"]
    for field in required_fields:
        if field in full_text:
            checks.append((f"欄位「{field}」", True, "已包含"))
        else:
            checks.append((f"欄位「{field}」", False, "缺少"))

    # 4. 發文日期檢查
    import re
    date_pattern = re.compile(r"中華民國\s*\d+\s*年\s*\d+\s*月\s*\d+\s*日")
    if date_pattern.search(full_text):
        checks.append(("發文日期", True, "格式正確"))
    else:
        checks.append(("發文日期", False, "缺少或格式不正確"))

    # 5. 發文字號檢查
    ref_pattern = re.compile(r"[\u4e00-\u9fff]+字第\s*\d+\s*號")
    if ref_pattern.search(full_text):
        checks.append(("發文字號", True, "格式正確"))
    else:
        checks.append(("發文字號", False, "缺少或格式不正確"))

    # 輸出結果
    table = Table(title="驗證結果", show_lines=True)
    table.add_column("檢查項目", style="cyan", width=14)
    table.add_column("狀態", width=6, justify="center")
    table.add_column("說明", width=30)

    pass_count = 0
    for name, ok, msg in checks:
        status = "[green]✓[/green]" if ok else "[red]✗[/red]"
        if ok:
            pass_count += 1
        table.add_row(name, status, msg)

    console.print(table)
    console.print(f"\n  通過：{pass_count}/{len(checks)} 項")

    if pass_count == len(checks):
        console.print("[bold green]  所有檢查通過！[/bold green]")
    else:
        console.print("[yellow]  部分檢查未通過，請檢查上方結果。[/yellow]")
