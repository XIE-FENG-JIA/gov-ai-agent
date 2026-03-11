"""使用者設定檔管理指令。"""

import json
import os

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()
_PROFILE_FILE = ".gov-ai-profile.json"


def _load_profile() -> dict:
    if os.path.isfile(_PROFILE_FILE):
        with open(_PROFILE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_profile(profile: dict):
    with open(_PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


@app.command()
def show(
    output_json: bool = typer.Option(False, "--json", help="以 JSON 格式輸出"),
):
    """顯示目前的個人設定檔。"""
    profile = _load_profile()
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
):
    """設定或更新個人資料鍵值。"""
    os.makedirs(profile_dir, exist_ok=True)
    settings_path = os.path.join(profile_dir, "settings.json")
    if os.path.isfile(settings_path):
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    data[key] = value
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    console.print(f"[green]已設定 {key} = {value}[/green]")


@app.command()
def clear():
    """清除個人設定檔。"""
    if os.path.isfile(_PROFILE_FILE):
        os.remove(_PROFILE_FILE)
    console.print("[green]個人資料已清除[/green]")
