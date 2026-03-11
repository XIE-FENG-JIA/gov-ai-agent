"""統計總覽指令。

顯示系統使用統計和知識庫概覽。
"""
import os
import json

from rich.console import Console
from rich.panel import Panel

console = Console()


def stats():
    """
    顯示系統使用統計和知識庫概覽。

    包含生成記錄統計、知識庫狀態和設定摘要。

    範例：

        gov-ai stats
    """
    console.print(Panel(
        "[bold cyan]公文 AI 助理 — 系統統計[/bold cyan]",
        border_style="cyan",
    ))

    # 1. 生成記錄統計
    console.print("\n[bold]生成記錄[/bold]")
    history_path = os.path.join(os.getcwd(), ".gov-ai-history.json")
    if os.path.isfile(history_path):
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                history = json.load(f)
            total = len(history)
            success = sum(1 for r in history if r.get("status") == "success")
            failed = total - success

            # 類型分佈
            type_counts: dict[str, int] = {}
            scores: list[float] = []
            for r in history:
                dt = r.get("doc_type", "未知")
                type_counts[dt] = type_counts.get(dt, 0) + 1
                if r.get("score") is not None:
                    scores.append(r["score"])

            console.print(f"  總計：{total} 筆（成功 {success}，失敗 {failed}）")
            if scores:
                avg_score = sum(scores) / len(scores)
                console.print(f"  平均品質分數：{avg_score:.2f}")

            if type_counts:
                sorted_types = sorted(type_counts.items(), key=lambda x: -x[1])
                top_types = ", ".join(f"{t}({c})" for t, c in sorted_types[:5])
                console.print(f"  類型分佈：{top_types}")
        except (json.JSONDecodeError, OSError):
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
