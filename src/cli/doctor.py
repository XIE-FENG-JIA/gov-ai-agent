"""系統診斷指令。

快速檢查並診斷常見問題。
"""
import os
import sys

from rich.console import Console
from rich.table import Table

console = Console()


def doctor():
    """
    快速診斷系統環境和常見問題。

    比 quickstart 更快速、更簡潔的診斷工具。

    範例：

        gov-ai doctor
    """
    checks: list[tuple[str, str, str]] = []  # (name, status_emoji, detail)

    # 1. Python 版本
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 10):
        checks.append(("Python", "✓", py_ver))
    else:
        checks.append(("Python", "✗", f"{py_ver}（需要 >= 3.10）"))

    # 2. config.yaml
    if os.path.isfile("config.yaml"):
        checks.append(("config.yaml", "✓", "存在"))
    else:
        checks.append(("config.yaml", "✗", "缺少 — 執行 gov-ai config init"))

    # 3. 知識庫目錄
    try:
        from src.core.config import ConfigManager
        config = ConfigManager().config
        kb_path = config.get("knowledge_base", {}).get("path", "./kb_data")
        if os.path.isdir(kb_path):
            checks.append(("知識庫目錄", "✓", kb_path))
        else:
            checks.append(("知識庫目錄", "△", f"{kb_path}（不存在，將自動建立）"))
    except (OSError, KeyError, ImportError, ValueError):
        checks.append(("知識庫目錄", "—", "無法檢查（設定檔缺失）"))

    # 4. LLM 提供者
    try:
        from src.core.config import ConfigManager
        config = ConfigManager().config
        llm_config = config.get("llm", {})
        provider = llm_config.get("provider", "未設定")
        model = llm_config.get("model", "未設定")
        checks.append(("LLM 提供者", "✓", f"{provider} / {model}"))
    except (OSError, KeyError, ImportError, ValueError):
        checks.append(("LLM 提供者", "✗", "無法讀取"))

    # 5. 必要套件
    missing_pkgs = []
    for pkg_name in ["docx", "yaml", "litellm", "rich", "typer"]:
        try:
            __import__(pkg_name)
        except ImportError:
            # docx 的 import 名稱不同
            if pkg_name == "docx":
                try:
                    __import__("docx")
                except ImportError:
                    missing_pkgs.append("python-docx")
            else:
                missing_pkgs.append(pkg_name)

    if not missing_pkgs:
        checks.append(("必要套件", "✓", "全部就緒"))
    else:
        checks.append(("必要套件", "✗", f"缺少：{', '.join(missing_pkgs)}"))

    # 輸出
    table = Table(title="系統診斷", show_lines=False, padding=(0, 1))
    table.add_column("項目", style="cyan", width=12)
    table.add_column("", width=3, justify="center")
    table.add_column("說明", width=45)

    for name, status, detail in checks:
        if status == "✓":
            s = "[green]✓[/green]"
        elif status == "✗":
            s = "[red]✗[/red]"
        elif status == "△":
            s = "[yellow]△[/yellow]"
        else:
            s = "[dim]—[/dim]"
        table.add_row(name, s, detail)

    console.print(table)

    has_error = any(s == "✗" for _, s, _ in checks)
    if has_error:
        console.print("\n[yellow]有項目需要修復。執行 gov-ai quickstart 取得詳細引導。[/yellow]")
    else:
        console.print("\n[green]系統就緒！[/green]")
