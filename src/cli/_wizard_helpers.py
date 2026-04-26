"""互動式公文精靈 — 輔助常數與函式。

從 wizard_cmd.py 拆出的資料常數與 UI 輔助函式，
以保持 wizard_cmd.py 在 350 行以下。
"""
from __future__ import annotations

import json
import os

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt

from src.cli.utils_io import resolve_state_read_path

console = Console()

# 12 種公文類型 — 依使用頻率排序
DOC_TYPES: list[tuple[str, str, str]] = [
    ("函",        "一般公文",         "機關間往復聯繫最常用，適合申請、通知、詢問等"),
    ("公告",      "對外公告",         "向公眾或特定對象宣布事項"),
    ("簽",        "內部簽呈",         "內部陳報、請示或提案，上簽長官核示"),
    ("書函",      "平行函文",         "與平行機關或民眾的正式往來文書"),
    ("令",        "行政命令",         "發布法規、命令或人事令"),
    ("開會通知單","會議通知",         "召集開會、通知與會人員"),
    ("呈",        "下級呈上級",       "下級機關向上級或向總統陳報"),
    ("咨",        "總統↔立法院",      "總統與立法院間的往復文書"),
    ("會勘通知單","現場勘查通知",     "通知相關單位到場會同勘查"),
    ("公務電話紀錄","電話溝通紀錄",   "記錄公務電話內容以備查考"),
    ("手令",      "首長指令",         "機關首長對所屬人員的指示命令"),
    ("箋函",      "機關內部簡便文書", "機關內部便箋、聯絡單等簡便文書"),
]

URGENCY_OPTIONS = ["普通", "速件", "最速件"]
_PROFILE_FILE = ".gov-ai-profile.json"


def _load_profile() -> dict:
    """載入個人設定檔（.gov-ai-profile.json），失敗時回傳空字典。"""
    try:
        profile_path = resolve_state_read_path(_PROFILE_FILE)
        if os.path.isfile(profile_path):
            with open(profile_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _show_type_menu() -> None:
    """顯示公文類型選單。"""
    table = Table(
        title="公文類型選單",
        show_header=True,
        header_style="bold cyan",
        show_lines=True,
        border_style="cyan",
    )
    table.add_column("序號", width=4, justify="right", style="dim")
    table.add_column("類型", width=10, style="bold yellow")
    table.add_column("說明", width=12, style="cyan")
    table.add_column("使用時機", style="dim")

    for i, (dtype, label, hint) in enumerate(DOC_TYPES, 1):
        table.add_row(str(i), dtype, label, hint)

    console.print(table)


def _select_doc_type() -> str:
    """互動選擇公文類型，傳回類型名稱。"""
    _show_type_menu()
    while True:
        raw = Prompt.ask(
            "\n[bold cyan]請選擇公文類型[/bold cyan] (輸入序號 1-12，或直接輸入類型名稱)",
            default="1",
        )
        # 數字選擇
        if raw.strip().isdigit():
            idx = int(raw.strip()) - 1
            if 0 <= idx < len(DOC_TYPES):
                chosen = DOC_TYPES[idx][0]
                console.print(f"  [green]✓[/green] 已選擇：[bold]{chosen}[/bold]（{DOC_TYPES[idx][1]}）")
                return chosen
            console.print(f"  [red]請輸入 1 到 {len(DOC_TYPES)} 之間的數字[/red]")
        else:
            # 名稱選擇
            names = [t[0] for t in DOC_TYPES]
            if raw.strip() in names:
                idx = names.index(raw.strip())
                console.print(f"  [green]✓[/green] 已選擇：[bold]{raw.strip()}[/bold]（{DOC_TYPES[idx][1]}）")
                return raw.strip()
            console.print(f"  [red]未知類型「{raw.strip()}」，請重新選擇[/red]")


def _build_input_text(
    doc_type: str,
    sender: str,
    receiver: str,
    subject: str,
    urgency: str,
    extra_context: str,
) -> str:
    """從精靈蒐集到的欄位組合成 generate -i 所需的自然語言描述。"""
    parts = [f"{sender}"]
    if doc_type in ("函", "書函", "呈", "咨", "箋函"):
        parts.append(f"發給{receiver}")
    elif doc_type == "公告":
        parts.append("公告")
    elif doc_type == "簽":
        parts.append("簽請")
    elif doc_type in ("令", "手令"):
        parts.append(f"發布{doc_type}")
    elif doc_type == "開會通知單":
        parts.append(f"通知{receiver}開會")
    elif doc_type == "會勘通知單":
        parts.append(f"通知{receiver}會勘")
    elif doc_type == "公務電話紀錄":
        parts.append(f"與{receiver}電話聯繫")
    else:
        parts.append(f"致{receiver}")

    parts.append(f"，主旨：{subject}")

    if urgency != "普通":
        parts.append(f"（{urgency}）")
    if extra_context:
        parts.append(f"，補充說明：{extra_context}")

    return "".join(parts)


def _show_summary(
    doc_type: str,
    sender: str,
    receiver: str,
    subject: str,
    urgency: str,
    output_path: str,
    date: str,
    cite: bool,
) -> None:
    """顯示即將生成的公文摘要。"""
    lines = [
        f"[bold]公文類型：[/bold]{doc_type}",
        f"[bold]發文機關：[/bold]{sender}",
        f"[bold]收文機關：[/bold]{receiver}",
        f"[bold]主  旨：[/bold]{subject}",
        f"[bold]速    別：[/bold]{urgency}",
        f"[bold]輸出路徑：[/bold]{output_path}",
    ]
    if date:
        lines.append(f"[bold]發文日期：[/bold]{date}")
    lines.append(f"[bold]法規引用：[/bold]{'自動顯示' if cite else '略過'}")

    console.print(Panel(
        "\n".join(lines),
        title="[bold green]公文精靈 — 生成摘要[/bold green]",
        border_style="green",
    ))
