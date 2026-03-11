"""組織記憶管理指令。

查看、管理和匯出機構偏好設定。
"""
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()


def _get_org_memory():
    """取得 OrganizationalMemory 實例。"""
    from src.core.config import ConfigManager
    from src.agents.org_memory import OrganizationalMemory

    config = ConfigManager().config
    storage_path = config.get("organizational_memory", {}).get(
        "storage_path", "./kb_data/agency_preferences.json"
    )
    return OrganizationalMemory(storage_path)


@app.command(name="list")
def list_agencies(
    category: str = typer.Option("", "--category", "-c", help="依正式程度篩選（standard/formal/concise）"),
):
    """列出所有已記錄的機構及其偏好摘要。"""
    try:
        om = _get_org_memory()
    except Exception as e:
        console.print(f"[red]無法載入組織記憶：{e}[/red]")
        raise typer.Exit(1)

    if not om.preferences:
        console.print("[yellow]尚無機構記憶。[/yellow]")
        console.print("[dim]系統將在使用過程中自動學習機構偏好。[/dim]")
        raise typer.Exit()

    items = list(om.preferences.items())
    if category:
        cat_val = category.lower().strip()
        items = [(n, p) for n, p in items if p.get("formal_level", "standard") == cat_val]
        if not items:
            console.print(f"[yellow]找不到正式程度為「{category}」的機構。[/yellow]")
            raise typer.Exit()
        console.print(f"  [dim]篩選條件：{category}[/dim]")

    table = Table(title="機構記憶", show_lines=True)
    table.add_column("機構名稱", style="cyan", width=24)
    table.add_column("正式程度", width=10, justify="center")
    table.add_column("偏好詞彙", width=8, justify="right")
    table.add_column("使用次數", width=8, justify="right")
    table.add_column("署名格式", width=16)

    for name, profile in sorted(
        items, key=lambda x: -x[1].get("usage_count", 0)
    ):
        table.add_row(
            name,
            profile.get("formal_level", "standard"),
            str(len(profile.get("preferred_terms", {}))),
            str(profile.get("usage_count", 0)),
            profile.get("signature_format", "default"),
        )

    console.print(table)
    console.print(f"[dim]共 {len(items)} 個機構[/dim]")


@app.command(name="show")
def show_agency(
    name: str = typer.Argument(..., help="機構名稱"),
):
    """顯示特定機構的詳細偏好設定。"""
    try:
        om = _get_org_memory()
    except Exception as e:
        console.print(f"[red]無法載入組織記憶：{e}[/red]")
        raise typer.Exit(1)

    if name not in om.preferences:
        console.print(f"[yellow]找不到機構「{name}」的記憶。[/yellow]")
        if om.preferences:
            available = ", ".join(list(om.preferences.keys())[:5])
            console.print(f"[dim]可用機構：{available}[/dim]")
        raise typer.Exit(1)

    profile = om.preferences[name]
    console.print(f"\n[bold cyan]{name}[/bold cyan]")
    console.print(f"  正式程度：{profile.get('formal_level', 'standard')}")
    console.print(f"  署名格式：{profile.get('signature_format', 'default')}")
    console.print(f"  使用次數：{profile.get('usage_count', 0)}")

    if profile.get("last_updated"):
        console.print(f"  最後更新：{profile['last_updated']}")

    terms = profile.get("preferred_terms", {})
    if terms:
        console.print(f"\n  [bold]偏好詞彙（{len(terms)} 項）：[/bold]")
        for old, new in list(terms.items())[:20]:
            console.print(f"    {old} -> {new}")
    else:
        console.print("\n  [dim]尚無偏好詞彙記錄。[/dim]")


@app.command(name="set")
def set_preference(
    agency_name: str = typer.Argument(..., help="機構名稱"),
    key: str = typer.Option(..., "--key", "-k", help="偏好項目（formal_level / signature_format）"),
    value: str = typer.Option(..., "--value", "-v", help="設定值"),
):
    """手動設定機構偏好。"""
    allowed_keys = {"formal_level", "signature_format"}
    if key not in allowed_keys:
        console.print(f"[red]不支援的偏好項目：{key}[/red]")
        console.print(f"[dim]可用項目：{', '.join(allowed_keys)}[/dim]")
        raise typer.Exit(1)

    if key == "formal_level" and value not in ("standard", "formal", "concise"):
        console.print("[red]formal_level 必須為 standard、formal 或 concise[/red]")
        raise typer.Exit(1)

    try:
        om = _get_org_memory()
        om.update_preference(agency_name, key, value)
    except Exception as e:
        console.print(f"[red]設定失敗：{e}[/red]")
        raise typer.Exit(1)


@app.command(name="add-term")
def add_term(
    agency_name: str = typer.Argument(..., help="機構名稱"),
    old_term: str = typer.Option(..., "--from", help="原始用語"),
    new_term: str = typer.Option(..., "--to", help="偏好用語"),
):
    """新增機構的偏好詞彙替換規則。"""
    try:
        om = _get_org_memory()
        profile = om.get_agency_profile(agency_name)
        terms = profile.get("preferred_terms", {})
        terms[old_term] = new_term
        om.update_preference(agency_name, "preferred_terms", terms)
        console.print(f"[green]已新增：「{old_term}」-> 「{new_term}」[/green]")
    except Exception as e:
        console.print(f"[red]設定失敗：{e}[/red]")
        raise typer.Exit(1)


@app.command(name="export")
def export_memory(
    output_path: str = typer.Option(
        "org_memory_export.json", "--output", "-o", help="匯出路徑"
    ),
):
    """匯出所有機構記憶為 JSON 檔案。"""
    try:
        om = _get_org_memory()
    except Exception as e:
        console.print(f"[red]無法載入組織記憶：{e}[/red]")
        raise typer.Exit(1)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(om.preferences, f, ensure_ascii=False, indent=2)
        console.print(f"[green]已匯出 {len(om.preferences)} 個機構的記憶至：{output_path}[/green]")
    except OSError as e:
        console.print(f"[red]匯出失敗：{e}[/red]")
        raise typer.Exit(1)


@app.command(name="report")
def report():
    """顯示機構記憶統計報告。"""
    try:
        om = _get_org_memory()
    except Exception as e:
        console.print(f"[red]無法載入組織記憶：{e}[/red]")
        raise typer.Exit(1)

    report_text = om.export_report()
    console.print(report_text)


@app.command(name="search")
def org_memory_search(
    keyword: str = typer.Argument(..., help="搜尋關鍵字"),
    memory_dir: str = typer.Option(".org_memory", "--dir", "-d", help="組織記憶目錄"),
):
    """搜尋組織記憶目錄中的檔案內容。"""
    mem_path = Path(memory_dir)
    if not mem_path.is_dir():
        console.print(f"[red]找不到組織記憶目錄：{memory_dir}[/red]")
        raise typer.Exit(1)

    suffixes = {".json", ".txt", ".md"}
    matched_files = 0
    results: list[tuple[str, list[str]]] = []

    for fp in sorted(mem_path.iterdir()):
        if not fp.is_file() or fp.suffix not in suffixes:
            continue
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            continue
        matched_lines = [
            line for line in content.splitlines() if keyword in line
        ]
        if matched_lines:
            matched_files += 1
            results.append((fp.name, matched_lines))

    if not results:
        console.print(f"[yellow]未找到包含「{keyword}」的內容。[/yellow]")
        raise typer.Exit()

    for filename, lines in results:
        console.print(f"\n[cyan]{filename}[/cyan]")
        for line in lines:
            console.print(f"  {line}")

    console.print(f"\n[green]找到 {matched_files} 筆符合的檔案。[/green]")
