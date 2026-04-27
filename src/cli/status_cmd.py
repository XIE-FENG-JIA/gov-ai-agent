"""系統狀態總覽儀表板指令。

讀取各項設定與記錄檔案，顯示系統整體狀態。
"""

import json as _json
import os

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.cli.utils_io import JSONStore

console = Console()

_history_store = JSONStore(".gov-ai-history.json", default=[])
_feedback_store = JSONStore(".gov-ai-feedback.json", default=[])
_profile_store = JSONStore(".gov-ai-profile.json", default={})
_aliases_store = JSONStore(".gov-ai-aliases.json", default={})
_CONFIG_FILE = "config.yaml"


def _load_config(path: str) -> dict | None:
    """嘗試載入 config.yaml，失敗回傳 None。"""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return None


def status(
    output_format: str = typer.Option("text", "--format", help="輸出格式：text（預設）或 json"),
):
    """
    顯示系統狀態總覽儀表板。

    彙整 LLM 設定、生成記錄、回饋記錄、使用者設定與別名數量。

    範例：

        gov-ai status
        gov-ai status --format json
    """
    if output_format not in {"text", "json"}:
        console.print(f"[red]錯誤：不支援的輸出格式 '{output_format}'，請使用 text 或 json。[/red]")
        raise typer.Exit(1)

    cwd = os.getcwd()
    config = _load_config(os.path.join(cwd, _CONFIG_FILE))
    history = _history_store.load()
    feedback = _feedback_store.load()

    history_count = len(history) if isinstance(history, list) else 0
    feedback_count = len(feedback) if isinstance(feedback, list) else 0

    # Determine kb_status
    kb_status = "unknown"
    try:
        from src.core.config import ConfigManager
        cfg = ConfigManager().config
        kb_path = cfg.get("knowledge_base", {}).get("path", "./kb_data")
        kb_status = "ok" if os.path.isdir(kb_path) else "missing"
    except (OSError, KeyError, ImportError, ValueError):
        kb_status = "error"

    if output_format == "json":
        print(_json.dumps({
            "config": config if config is not None else {},
            "history_count": history_count,
            "feedback_count": feedback_count,
            "kb_status": kb_status,
        }, ensure_ascii=False))
        return

    # ── 文字輸出 ──────────────────────────────────────────────────
    table = Table(show_header=True, header_style="bold cyan", expand=True)
    table.add_column("項目", style="bold")
    table.add_column("狀態")
    table.add_column("詳情")

    # 1. LLM 設定
    if config:
        llm = config.get("llm", {})
        provider = llm.get("provider", "未指定")
        model = llm.get("model", "未指定")
        table.add_row("LLM 設定", "[green]✓ 已設定[/green]", f"{provider} / {model}")
    else:
        table.add_row("LLM 設定", "[dim]✗ 未設定[/dim]", "[dim]尚未建立 config.yaml[/dim]")

    # 2. 生成記錄
    if isinstance(history, list) and history:
        table.add_row("生成記錄", "[green]✓ 已設定[/green]", f"{history_count} 筆")
    else:
        table.add_row("生成記錄", "[dim]✗ 未設定[/dim]", "[dim]尚無記錄[/dim]")

    # 3. 回饋記錄
    if isinstance(feedback, list) and feedback:
        scores = [r.get("score") for r in feedback if isinstance(r.get("score"), (int, float))]
        avg = sum(scores) / len(scores) if scores else 0
        detail = f"{feedback_count} 筆"
        if scores:
            detail += f"，平均 {avg:.1f} 分"
        table.add_row("回饋記錄", "[green]✓ 已設定[/green]", detail)
    else:
        table.add_row("回饋記錄", "[dim]✗ 未設定[/dim]", "[dim]尚無回饋[/dim]")

    # 4. 使用者設定
    profile = _profile_store.load()
    if isinstance(profile, dict) and profile:
        table.add_row("使用者設定", "[green]✓ 已設定[/green]", f"{len(profile)} 項欄位")
    else:
        table.add_row("使用者設定", "[dim]✗ 未設定[/dim]", "[dim]尚未建立[/dim]")

    # 5. 別名數量
    aliases = _aliases_store.load()
    if isinstance(aliases, dict) and aliases:
        table.add_row("指令別名", "[green]✓ 已設定[/green]", f"{len(aliases)} 組")
    else:
        table.add_row("指令別名", "[dim]✗ 未設定[/dim]", "[dim]尚未建立[/dim]")

    console.print(Panel(table, title="公文 AI 助理 — 系統狀態", border_style="cyan"))
