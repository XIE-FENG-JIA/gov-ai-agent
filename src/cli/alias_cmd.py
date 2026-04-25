import json
import os
import typer
from rich.console import Console
from rich.table import Table

from src.cli.utils_io import JSONStore

app = typer.Typer()
console = Console()
_alias_store = JSONStore(".gov-ai-aliases.json", default={})


@app.command("add")
def add(
    name: str = typer.Argument(..., help="別名名稱"),
    command: str = typer.Argument(..., help="對應的指令"),
) -> None:
    """新增或覆蓋指令別名。"""
    aliases = _alias_store.load()
    if name in aliases:
        console.print(f"[yellow]別名 '{name}' 已存在，將覆蓋舊值。[/yellow]")
    aliases[name] = command
    _alias_store.save(aliases)
    console.print(f"[green]已新增別名：{name} → {command}[/green]")


@app.command("list")
def list_aliases(
    output_json: bool = typer.Option(False, "--json", help="以 JSON 格式輸出"),
) -> None:
    """列出所有已設定的別名。"""
    aliases = _alias_store.load()
    if not aliases:
        console.print("[yellow]目前沒有任何別名。[/yellow]")
        return

    if output_json:
        import json as json_mod
        console.print(json_mod.dumps(aliases, ensure_ascii=False, indent=2))
        return

    table = Table(title="指令別名")
    table.add_column("別名", style="cyan")
    table.add_column("指令", style="green")
    for name, command in aliases.items():
        table.add_row(name, command)
    console.print(table)


@app.command("remove")
def remove(
    name: str = typer.Argument(..., help="要刪除的別名名稱"),
) -> None:
    """刪除指定的別名。"""
    aliases = _alias_store.load()
    if name not in aliases:
        console.print(f"[red]別名 '{name}' 不存在。[/red]")
        raise typer.Exit(code=1)
    del aliases[name]
    _alias_store.save(aliases)
    console.print(f"[green]已刪除別名：{name}[/green]")


@app.command("rename")
def rename_alias(
    old_name: str = typer.Argument(..., help="目前的別名名稱"),
    new_name: str = typer.Argument(..., help="新的別名名稱"),
) -> None:
    """重新命名指定的別名。"""
    aliases = _alias_store.load()
    if old_name not in aliases:
        console.print(f"[red]別名 '{old_name}' 不存在。[/red]")
        raise typer.Exit(code=1)
    if new_name in aliases:
        console.print(f"[yellow]別名 '{new_name}' 已存在。[/yellow]")
        raise typer.Exit(code=1)
    aliases[new_name] = aliases.pop(old_name)
    _alias_store.save(aliases)
    console.print(f"[green]已重新命名：{old_name} → {new_name}[/green]")


@app.command("import")
def import_aliases(
    file: str = typer.Argument(..., help="JSON 別名檔案路徑"),
) -> None:
    """從 JSON 檔案匯入別名。"""
    if not os.path.isfile(file):
        console.print(f"[red]找不到檔案：{file}[/red]")
        raise typer.Exit(code=1)
    try:
        with open(file, "r", encoding="utf-8") as f:
            new_aliases = json.load(f)
    except (json.JSONDecodeError, OSError):
        console.print("[red]JSON 格式錯誤。[/red]")
        raise typer.Exit(code=1)
    if not isinstance(new_aliases, dict):
        console.print("[red]JSON 內容必須為物件（key-value 映射）。[/red]")
        raise typer.Exit(code=1)
    aliases = _alias_store.load()
    count = 0
    for name, command in new_aliases.items():
        if isinstance(command, str):
            aliases[name] = command
            count += 1
    _alias_store.save(aliases)
    console.print(f"[green]已匯入 {count} 個別名。[/green]")
