"""使用者設定檔管理指令。"""

import json
import os

import typer
from typer.models import OptionInfo
from rich.console import Console
from rich.table import Table

from src.cli.utils_io import JSONStore, atomic_json_write, resolve_state_path, resolve_state_read_path

app = typer.Typer()
console = Console()
_PROFILE_FILE = ".gov-ai-profile.json"
_profile_store = JSONStore(_PROFILE_FILE, default={})


def _resolve_profile_dir(profile_dir: str, *, for_write: bool) -> str:
    if isinstance(profile_dir, OptionInfo):
        profile_dir = profile_dir.default
    if not for_write:
        return resolve_state_read_path(profile_dir)
    read_path = resolve_state_read_path(profile_dir)
    write_path = resolve_state_path(profile_dir)
    if read_path != write_path and os.path.isdir(read_path) and not os.path.exists(write_path):
        return read_path
    return write_path


@app.command()
def show(
    output_json: bool = typer.Option(False, "--json", help="以 JSON 格式輸出"),
) -> None:
    """顯示目前的個人設定檔。"""
    profile = _profile_store.load()
    if not profile:
        if output_json:
            console.print("{}")
        else:
            console.print("[yellow]尚未設定個人資料[/yellow]")
        raise typer.Exit()

    if output_json:
        import json as json_mod
        console.print(json_mod.dumps(profile, ensure_ascii=False, indent=2))
        return

    table = Table(title="個人設定檔")
    table.add_column("欄位", style="cyan")
    table.add_column("值", style="green")

    labels = {"name": "姓名", "title": "職稱", "agency": "機關", "email": "信箱"}
    for key, label in labels.items():
        value = profile.get(key, "")
        if value:
            table.add_row(label, value)

    console.print(table)


@app.command(name="set")
def profile_set(
    key: str = typer.Argument(..., help="設定鍵名"),
    value: str = typer.Argument(..., help="設定值"),
    profile_dir: str = typer.Option(".profile", "--dir", help="設定檔目錄"),
) -> None:
    """設定或更新個人資料鍵值。"""
    resolved_dir = _resolve_profile_dir(profile_dir, for_write=True)
    os.makedirs(resolved_dir, exist_ok=True)
    settings_path = os.path.join(resolved_dir, "settings.json")
    if os.path.isfile(settings_path):
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    data[key] = value
    atomic_json_write(settings_path, data)
    console.print(f"[green]已設定 {key} = {value}[/green]")


@app.command()
def clear() -> None:
    """清除個人設定檔。"""
    if os.path.isfile(_PROFILE_FILE):
        try:
            os.remove(_PROFILE_FILE)
        except OSError as exc:
            console.print(f"[red]無法刪除設定檔（可能被其他程序佔用）: {exc}[/red]")
            return
    console.print("[green]個人資料已清除[/green]")
