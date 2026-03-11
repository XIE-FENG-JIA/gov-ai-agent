import json
import os
import zipfile
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table

console = Console()


def archive(
    files: list[str] = typer.Argument(..., help="要封存的公文檔案路徑"),
    output: str = typer.Option("", "-o", "--output", help="ZIP 輸出路徑（預設：archive_YYYYMMDD.zip）"),
    tag: str = typer.Option("", "--tag", help="封存標籤"),
    password: str = typer.Option("", "--password", "-p", help="設定封存密碼（記錄於 metadata）"),
):
    """將公文檔案封存為 ZIP 壓縮檔。"""
    if not files:
        console.print("[red]錯誤：請指定至少一個檔案。[/red]")
        raise typer.Exit(1)

    # 驗證檔案存在
    for f in files:
        if not os.path.isfile(f):
            console.print(f"[red]錯誤：找不到檔案：{f}[/red]")
            raise typer.Exit(1)

    # 決定輸出路徑
    if not output:
        output = f"archive_{datetime.now().strftime('%Y%m%d')}.zip"

    # 建立 ZIP
    metadata = {
        "created_at": datetime.now().isoformat(),
        "tag": tag or "",
        "files": [os.path.basename(f) for f in files],
        "password_protected": bool(password),
    }

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, os.path.basename(f))
        zf.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))

    # 顯示結果
    zip_size = os.path.getsize(output)
    table = Table(title="封存檔案清單")
    table.add_column("檔案", style="cyan")
    table.add_column("大小", style="green", justify="right")

    for f in files:
        size = os.path.getsize(f)
        table.add_row(os.path.basename(f), f"{size:,} bytes")

    console.print(table)
    if tag:
        console.print(f"  標籤：[bold]{tag}[/bold]")
    if password:
        console.print("  [yellow]密碼保護：已啟用（請妥善保管密碼）[/yellow]")
    console.print(f"\n[green]已封存 {len(files)} 個檔案至 {output}（{zip_size:,} bytes）[/green]")
