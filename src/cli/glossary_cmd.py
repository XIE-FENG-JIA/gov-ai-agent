import json
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from src.cli.utils_io import atomic_json_write

logger = logging.getLogger(__name__)

app = typer.Typer()
console = Console()

# 公文語彙庫
_GLOSSARY = {
    "起首語": {
        "查": "用於引述過去的事實或法規",
        "准": "用於引述來函",
        "奉": "用於引述上級機關來函",
        "茲": "用於開始說明事項",
        "案": "用於引述案由",
        "遵": "用於引述上級指示",
    },
    "連接語": {
        "爰": "因此、所以（較正式）",
        "惟": "但是、然而",
        "另": "此外",
        "復": "又、再",
        "嗣": "後來",
        "迨": "等到",
    },
    "結尾語": {
        "請查照": "對平行機關或下級機關",
        "請核示": "對上級機關請求指示",
        "請鑒核": "對上級機關請求核准",
        "請照辦": "對下級機關要求辦理",
        "請轉行照辦": "請受文者轉發相關單位辦理",
        "希照辦": "對下級機關（較嚴肅）",
    },
    "稱謂語": {
        "鈞": "下級對上級的敬稱",
        "貴": "對平行機關的敬稱",
        "本": "自稱（本機關、本局）",
        "該": "指稱第三方機關",
        "台端": "對個人的敬稱",
    },
}


@app.command("list")
def list_categories() -> None:
    """列出所有公文語彙分類。"""
    table = Table(title="公文語彙分類")
    table.add_column("分類", style="cyan")
    table.add_column("語彙數量", justify="right", style="green")
    for category, terms in _GLOSSARY.items():
        table.add_row(category, str(len(terms)))
    console.print(table)


@app.command("search")
def search(
    keyword: str = typer.Argument(..., help="搜尋關鍵字"),
    fuzzy: bool = typer.Option(False, "--fuzzy", help="啟用模糊搜尋（部分匹配）"),
) -> None:
    """搜尋公文語彙（名稱或說明）。"""
    table = Table(title=f"搜尋結果：{keyword}")
    table.add_column("分類", style="cyan")
    table.add_column("語彙", style="yellow")
    table.add_column("說明", style="white")
    found = False
    for category, terms in _GLOSSARY.items():
        for term, description in terms.items():
            if fuzzy:
                # 模糊搜尋：keyword 中任一字元出現在 term 或 description 中即匹配
                if any(ch in term or ch in description for ch in keyword):
                    table.add_row(category, term, description)
                    found = True
            else:
                if keyword in term or keyword in description:
                    table.add_row(category, term, description)
                    found = True
    if fuzzy:
        console.print("  [dim]搜尋模式：模糊搜尋[/dim]")
    if found:
        console.print(table)
    else:
        console.print(f"[yellow]找不到包含「{keyword}」的語彙。[/yellow]")


def _load_glossary_entries(path: Path) -> list[dict]:
    """從 JSON 檔案載入語彙清單，損壞時回傳空清單並警告。"""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("語彙檔案損壞 %s：%s，將以空清單重建", path, exc)
        console.print(f"[yellow]警告：語彙檔案 {path} 格式損壞，將從空白開始。[/yellow]")
        return []
    if not isinstance(data, list):
        logger.warning("語彙檔案 %s 非陣列格式，將以空清單重建", path)
        console.print(f"[yellow]警告：語彙檔案 {path} 格式不正確，將從空白開始。[/yellow]")
        return []
    return data


@app.command(name="add")
def glossary_add(
    term: str = typer.Argument(..., help="語彙"),
    definition: str = typer.Argument(..., help="定義/說明"),
    glossary_file: str = typer.Option(
        ".glossary/custom.json", "--file", "-f", help="語彙檔案路徑"
    ),
) -> None:
    """新增或更新自訂語彙。"""
    path = Path(glossary_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    entries: list[dict] = _load_glossary_entries(path)

    # 檢查是否已有相同 term
    for entry in entries:
        if entry.get("term") == term:
            entry["definition"] = definition
            atomic_json_write(str(path), entries)
            console.print(f"[green]已更新語彙：{term}[/green]")
            return

    entries.append({"term": term, "definition": definition})
    atomic_json_write(str(path), entries)
    console.print(f"[green]已新增語彙：{term}[/green]")


@app.command(name="remove")
def glossary_remove(
    term: str = typer.Argument(..., help="要刪除的語彙"),
    glossary_file: str = typer.Option(
        ".glossary/custom.json", "--file", "-f", help="語彙檔案路徑"
    ),
) -> None:
    """刪除自訂語彙。"""
    path = Path(glossary_file)
    if not path.exists():
        console.print("[red]找不到語彙檔案。[/red]")
        raise typer.Exit(1)

    entries = _load_glossary_entries(path)
    original_len = len(entries)
    entries = [e for e in entries if e.get("term") != term]

    if len(entries) == original_len:
        console.print(f"[yellow]找不到語彙「{term}」。[/yellow]")
        raise typer.Exit(1)

    atomic_json_write(str(path), entries)
    console.print(f"[green]已刪除語彙：{term}[/green]")
