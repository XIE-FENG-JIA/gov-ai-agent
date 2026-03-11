"""系統狀態總覽儀表板指令。

讀取各項設定與記錄檔案，顯示系統整體狀態。
"""

import json
import os

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

_HISTORY_FILE = ".gov-ai-history.json"
_FEEDBACK_FILE = ".gov-ai-feedback.json"
_PROFILE_FILE = ".gov-ai-profile.json"
_ALIASES_FILE = ".gov-ai-aliases.json"
_CONFIG_FILE = "config.yaml"


def _load_json(path: str) -> list | dict | None:
    """嘗試載入 JSON 檔案，失敗回傳 None。"""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _load_config(path: str) -> dict | None:
    """嘗試載入 config.yaml，失敗回傳 None。"""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return None


def status():
    """
    顯示系統狀態總覽儀表板。

    彙整 LLM 設定、生成記錄、回饋記錄、使用者設定與別名數量。

    範例：

        gov-ai status
    """
    cwd = os.getcwd()

    table = Table(show_header=True, header_style="bold cyan", expand=True)
    table.add_column("項目", style="bold")
    table.add_column("狀態")
    table.add_column("詳情")

    # 1. LLM 設定
    config = _load_config(os.path.join(cwd, _CONFIG_FILE))
    if config:
        llm = config.get("llm", {})
        provider = llm.get("provider", "未指定")
        model = llm.get("model", "未指定")
        table.add_row("LLM 設定", "[green]✓ 已設定[/green]", f"{provider} / {model}")
    else:
        table.add_row("LLM 設定", "[dim]✗ 未設定[/dim]", "[dim]尚未建立 config.yaml[/dim]")

    # 2. 生成記錄
    history = _load_json(os.path.join(cwd, _HISTORY_FILE))
    if isinstance(history, list) and history:
        table.add_row("生成記錄", "[green]✓ 已設定[/green]", f"{len(history)} 筆")
    else:
        table.add_row("生成記錄", "[dim]✗ 未設定[/dim]", "[dim]尚無記錄[/dim]")

    # 3. 回饋記錄
    feedback = _load_json(os.path.join(cwd, _FEEDBACK_FILE))
    if isinstance(feedback, list) and feedback:
        scores = [r.get("score") for r in feedback if isinstance(r.get("score"), (int, float))]
        avg = sum(scores) / len(scores) if scores else 0
        detail = f"{len(feedback)} 筆"
        if scores:
            detail += f"，平均 {avg:.1f} 分"
        table.add_row("回饋記錄", "[green]✓ 已設定[/green]", detail)
    else:
        table.add_row("回饋記錄", "[dim]✗ 未設定[/dim]", "[dim]尚無回饋[/dim]")

    # 4. 使用者設定
    profile = _load_json(os.path.join(cwd, _PROFILE_FILE))
    if isinstance(profile, dict) and profile:
        table.add_row("使用者設定", "[green]✓ 已設定[/green]", f"{len(profile)} 項欄位")
    else:
        table.add_row("使用者設定", "[dim]✗ 未設定[/dim]", "[dim]尚未建立[/dim]")

    # 5. 別名數量
    aliases = _load_json(os.path.join(cwd, _ALIASES_FILE))
    if isinstance(aliases, dict) and aliases:
        table.add_row("指令別名", "[green]✓ 已設定[/green]", f"{len(aliases)} 組")
    else:
        table.add_row("指令別名", "[dim]✗ 未設定[/dim]", "[dim]尚未建立[/dim]")

    console.print(Panel(table, title="公文 AI 助理 — 系統狀態", border_style="cyan"))
