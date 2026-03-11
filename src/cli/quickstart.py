"""快速開始引導指令。

為首次使用者提供 step-by-step 的環境檢查與設置引導。
"""
import os
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from src.core.constants import CONNECTIVITY_CHECK_TIMEOUT

console = Console()


def quickstart():
    """快速開始引導：檢查環境、設定並產生範例公文。

    自動檢查系統環境是否就緒，並引導完成初始設置。
    """
    console.print(Panel(
        "[bold cyan]公文 AI 助理 — 快速開始引導[/bold cyan]\n\n"
        "此引導將檢查您的系統環境，並協助完成初始設置。",
        border_style="cyan",
    ))

    checks: list[tuple[str, bool, str]] = []

    # 1. 檢查 config.yaml
    console.print("\n[bold]1. 檢查設定檔[/bold]")
    config_exists = os.path.isfile("config.yaml")
    if config_exists:
        console.print("  [green]✓[/green] config.yaml 已存在")
        checks.append(("設定檔", True, "已就緒"))
    else:
        console.print("  [red]✗[/red] config.yaml 不存在")
        console.print("  [dim]請從範本建立：cp config.yaml.example config.yaml[/dim]")
        checks.append(("設定檔", False, "缺少 config.yaml"))

    # 2. 檢查 LLM 連線
    console.print("\n[bold]2. 檢查 LLM 連線[/bold]")
    llm_ok = False
    llm_msg = "未檢查"
    if config_exists:
        try:
            from src.core.config import ConfigManager
            from src.core.llm import get_llm_factory, LiteLLMProvider
            config = ConfigManager().config
            llm_config = config.get("llm")
            if llm_config:
                llm = get_llm_factory(llm_config, full_config=config)
                if isinstance(llm, LiteLLMProvider):
                    ok, err = llm.check_connectivity(timeout=CONNECTIVITY_CHECK_TIMEOUT)
                    if ok:
                        console.print(f"  [green]✓[/green] LLM 連線正常（{llm_config.get('provider', '?')}）")
                        llm_ok = True
                        llm_msg = f"{llm_config.get('provider', '?')} 連線正常"
                    else:
                        console.print(f"  [red]✗[/red] LLM 連線失敗：{err}")
                        llm_msg = f"連線失敗：{err}"
                        _print_llm_fix_hint(llm_config.get("provider", ""))
                else:
                    console.print("  [green]✓[/green] LLM 提供者已設定")
                    llm_ok = True
                    llm_msg = "已設定"
            else:
                console.print("  [red]✗[/red] config.yaml 缺少 llm 區塊")
                llm_msg = "缺少 llm 設定"
        except Exception as exc:
            console.print(f"  [red]✗[/red] LLM 初始化失敗：{str(exc)[:60]}")
            llm_msg = f"初始化失敗：{str(exc)[:40]}"
    else:
        console.print("  [yellow]—[/yellow] 跳過（缺少設定檔）")
        llm_msg = "跳過"
    checks.append(("LLM 連線", llm_ok, llm_msg))

    # 3. 檢查知識庫
    console.print("\n[bold]3. 檢查知識庫[/bold]")
    kb_ok = False
    kb_msg = "未檢查"
    if config_exists and llm_ok:
        try:
            from src.core.config import ConfigManager
            from src.core.llm import get_llm_factory
            from src.knowledge.manager import KnowledgeBaseManager
            config = ConfigManager().config
            llm_config = config.get("llm")
            kb_path = config.get("knowledge_base", {}).get("path", "./kb_data")
            llm = get_llm_factory(llm_config, full_config=config)
            kb = KnowledgeBaseManager(kb_path, llm)
            stats = kb.get_stats()
            examples_count = stats.get("examples_count", 0)
            if examples_count > 0:
                console.print(f"  [green]✓[/green] 知識庫已初始化（{examples_count} 筆範例）")
                kb_ok = True
                kb_msg = f"{examples_count} 筆範例"
            else:
                console.print("  [yellow]△[/yellow] 知識庫尚未匯入範例（系統仍可運作，但品質可能受限）")
                console.print("  [dim]建議執行：gov-ai kb ingest[/dim]")
                kb_msg = "未匯入範例"
        except Exception as exc:
            console.print(f"  [yellow]△[/yellow] 知識庫檢查失敗：{str(exc)[:60]}")
            kb_msg = f"檢查失敗：{str(exc)[:40]}"
    else:
        console.print("  [yellow]—[/yellow] 跳過（前置條件未滿足）")
        kb_msg = "跳過"
    checks.append(("知識庫", kb_ok, kb_msg))

    # 4. 摘要表格
    console.print()
    table = Table(title="環境檢查摘要", show_lines=True)
    table.add_column("項目", style="cyan", width=12)
    table.add_column("狀態", width=6, justify="center")
    table.add_column("說明", width=40)

    all_ok = True
    for name, ok, msg in checks:
        status = "[green]✓[/green]" if ok else "[red]✗[/red]"
        if not ok:
            all_ok = False
        table.add_row(name, status, msg)
    console.print(table)

    # 5. 下一步指引
    console.print()
    if all_ok:
        console.print(Panel(
            "[bold green]環境檢查通過！[/bold green]\n\n"
            "您可以開始使用公文 AI 助理：\n\n"
            '  [cyan]gov-ai generate -i "台北市環保局發給各學校，加強資源回收"[/cyan]\n\n'
            "其他常用指令：\n"
            "  [dim]gov-ai types[/dim]        列出支援的公文類型\n"
            "  [dim]gov-ai kb search TEXT[/dim] 搜尋知識庫\n"
            "  [dim]gov-ai config show[/dim]   查看目前設定",
            title="下一步",
            border_style="green",
        ))
    else:
        console.print(Panel(
            "[bold yellow]部分環境尚未就緒[/bold yellow]\n\n"
            "請依照上方提示完成設置，然後重新執行：\n\n"
            "  [cyan]gov-ai quickstart[/cyan]",
            title="下一步",
            border_style="yellow",
        ))


def _print_llm_fix_hint(provider: str):
    """根據 LLM 提供者印出修復提示。"""
    if provider == "ollama":
        console.print("  [dim]Ollama 用戶請確認已啟動服務：ollama serve[/dim]")
        console.print("  [dim]並下載模型：ollama pull llama3.1:8b[/dim]")
    elif provider == "gemini":
        console.print("  [dim]Gemini 用戶請設定 API Key：export GEMINI_API_KEY=your-key[/dim]")
    elif provider == "openrouter":
        console.print("  [dim]OpenRouter 用戶請設定：export LLM_API_KEY=your-key[/dim]")
    else:
        console.print("  [dim]請檢查 config.yaml 中的 LLM 設定。[/dim]")
