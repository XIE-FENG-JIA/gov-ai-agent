from pathlib import Path

import typer
from rich.console import Console

console = Console()


def replace_text(
    file_path: str = typer.Argument(..., help="公文檔案路徑"),
    old: str = typer.Option(..., "--old", help="要替換的文字"),
    new: str = typer.Option(..., "--new", help="替換成的文字"),
    count: int = typer.Option(0, "--count", "-c", help="替換次數（0=全部）"),
    backup: bool = typer.Option(False, "--backup", "-b", help="替換前備份原始檔案"),
):
    """批量替換公文中的指定文字。"""
    path = Path(file_path)
    if not path.exists():
        console.print("[red]錯誤：找不到檔案[/red]")
        raise typer.Exit(1)

    content = path.read_text(encoding="utf-8")

    if old not in content:
        console.print(f"[yellow]未找到「{old}」[/yellow]")
        return

    if count == 0:
        replaced = content.replace(old, new)
        n = content.count(old)
    else:
        replaced = content.replace(old, new, count)
        n = min(count, content.count(old))

    if backup:
        import shutil
        backup_path = str(path) + ".bak"
        shutil.copy2(str(path), backup_path)
        console.print(f"[dim]已備份至：{backup_path}[/dim]")

    path.write_text(replaced, encoding="utf-8")
    console.print(f"[green]已替換 {n} 處[/green]")
