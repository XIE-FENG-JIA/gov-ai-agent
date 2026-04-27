"""統計總覽指令。

顯示系統使用統計和知識庫概覽。
"""
import json as _json
import os

import typer
from rich.console import Console
from rich.panel import Panel

from src.cli.utils_io import JSONStore

console = Console()

_history_store = JSONStore(".gov-ai-history.json", default=[])


def stats(
    output_format: str = typer.Option("text", "--format", help="輸出格式：text（預設）或 json"),
):
    """
    顯示系統使用統計和知識庫概覽。

    包含生成記錄統計、知識庫狀態和設定摘要。

    範例：

        gov-ai stats
        gov-ai stats --format json
    """
    if output_format not in {"text", "json"}:
        console.print(f"[red]錯誤：不支援的輸出格式 '{output_format}'，請使用 text 或 json。[/red]")
        raise typer.Exit(1)

    # ── 收集統計資料 ──────────────────────────────────────────────
    total = 0
    success = 0
    failed = 0
    type_counts: dict[str, int] = {}
    avg_score: float | None = None

    if _history_store.exists():
        history = _history_store.load()
        if isinstance(history, list):
            total = len(history)
            success = sum(1 for r in history if r.get("status") == "success")
            failed = total - success
            scores: list[float] = []
            for r in history:
                dt = r.get("doc_type", "未知")
                type_counts[dt] = type_counts.get(dt, 0) + 1
                if r.get("score") is not None:
                    scores.append(r["score"])
            if scores:
                avg_score = sum(scores) / len(scores)

    if output_format == "json":
        print(_json.dumps({
            "total": total,
            "success": success,
            "failed": failed,
            "type_counts": type_counts,
            "avg_score": avg_score,
        }, ensure_ascii=False))
        return

    # ── 文字輸出 ──────────────────────────────────────────────────
    console.print(Panel(
        "[bold cyan]公文 AI 助理 — 系統統計[/bold cyan]",
        border_style="cyan",
    ))

    # 1. 生成記錄統計
    console.print("\n[bold]生成記錄[/bold]")
    if _history_store.exists():
        history = _history_store.load()
        if isinstance(history, list):
            console.print(f"  總計：{total} 筆（成功 {success}，失敗 {failed}）")
            if avg_score is not None:
                console.print(f"  平均品質分數：{avg_score:.2f}")
            if type_counts:
                sorted_types = sorted(type_counts.items(), key=lambda x: -x[1])
                top_types = ", ".join(f"{t}({c})" for t, c in sorted_types[:5])
                console.print(f"  類型分佈：{top_types}")
        else:
            console.print("  [yellow]歷史記錄檔案損壞[/yellow]")
    else:
        console.print("  [dim]尚無記錄（使用 gov-ai generate 後自動產生）[/dim]")

    # 2. 知識庫狀態
    console.print("\n[bold]知識庫狀態[/bold]")
    try:
        from src.core.config import ConfigManager
        config = ConfigManager().config
        kb_path = config.get("knowledge_base", {}).get("path", "./kb_data")
        if os.path.isdir(kb_path):
            file_count = sum(1 for f in os.listdir(kb_path) if os.path.isfile(os.path.join(kb_path, f)))
            console.print(f"  路徑：{kb_path}")
            console.print(f"  檔案數：{file_count}")
        else:
            console.print(f"  [yellow]知識庫目錄不存在：{kb_path}[/yellow]")
    except (OSError, KeyError, ImportError, ValueError):
        console.print("  [dim]無法讀取知識庫狀態[/dim]")

    # 3. 設定摘要
    console.print("\n[bold]目前設定[/bold]")
    try:
        from src.core.config import ConfigManager
        config = ConfigManager().config
        llm = config.get("llm", {})
        console.print(f"  LLM 提供者：{llm.get('provider', '未設定')}")
        console.print(f"  模型：{llm.get('model', '未設定')}")
    except (OSError, KeyError, ImportError, ValueError):
        console.print("  [dim]無法讀取設定[/dim]")
