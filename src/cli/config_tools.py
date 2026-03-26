import json
import logging
import typer
import requests
import yaml
import os
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm, Prompt
from src.core.config import ConfigManager
from src.core.llm import LiteLLMProvider
from src.cli.utils import atomic_yaml_write

logger = logging.getLogger(__name__)

console = Console()
app = typer.Typer()

def test_connectivity(model_id: str, api_key: str) -> bool:
    """嘗試使用模型產生簡短回應以測試連線。"""
    if not api_key:
        return False

    # Construct provider config
    # We assume OpenRouter because this tool fetches from OpenRouter
    config = {
        "provider": "openrouter",
        "model": model_id,
        "api_key": api_key,
        "base_url": "https://openrouter.ai/api/v1"
    }

    try:
        llm = LiteLLMProvider(config)
        # Very short prompt to save time/tokens
        llm.generate("Hi", max_tokens=1)
        return True
    except Exception as exc:
        logger.debug("模型連線測試失敗（%s）: %s", model_id, exc)
        return False

@app.command()
def show(
    format: str = typer.Option("yaml", "--format", help="輸出格式（yaml 或 json）"),
    section: str = typer.Option(
        "", "--section", "-s",
        help="僅顯示特定區段（llm/knowledge_base/api/organizational_memory）",
    ),
) -> None:
    """
    顯示目前的組態設定。

    範例：

        gov-ai config show

        gov-ai config show --format json

        gov-ai config show --section llm
    """
    if format not in ("yaml", "json"):
        console.print(f"[red]不支援的格式：{format}（請使用 yaml 或 json）[/red]")
        raise typer.Exit(1)

    cm = ConfigManager()
    config = cm.config

    if section:
        sec_val = section.lower().strip()
        if sec_val in config:
            section_data = {sec_val: config[sec_val]}
            if format == "json":
                console.print(json.dumps(section_data, ensure_ascii=False, indent=2))
            else:
                console.print(f"\n[bold cyan]{sec_val} 設定區段：[/bold cyan]")
                for k, v in (config[sec_val] if isinstance(config[sec_val], dict) else {}).items():
                    console.print(f"  {k}: {v}")
            console.print(f"\n  [dim]區段篩選：{sec_val}[/dim]")
            return
        else:
            console.print(f"[yellow]找不到區段：{section}（可用：{', '.join(config.keys())}）[/yellow]")
            raise typer.Exit(1)

    if format == "json":
        console.print(json.dumps(config, ensure_ascii=False, indent=2))
        return

    table = Table(title="目前組態設定", show_lines=True)
    table.add_column("設定項", style="cyan", no_wrap=True)
    table.add_column("值", style="green")

    # LLM 設定
    llm = config.get("llm", {})
    table.add_row("LLM 提供者", llm.get("provider", "未設定"))
    table.add_row("LLM 模型", llm.get("model", "未設定"))
    table.add_row("LLM Base URL", llm.get("base_url", "未設定"))
    api_key = llm.get("api_key", "")
    table.add_row("API Key", f"{'****' + api_key[-4:] if api_key and len(api_key) > 4 else '（未設定）'}")

    # Embedding 設定
    table.add_row("Embedding 提供者", llm.get("embedding_provider", "未設定"))
    table.add_row("Embedding 模型", llm.get("embedding_model", "未設定"))
    table.add_row("Embedding Base URL", llm.get("embedding_base_url", "未設定"))

    # 知識庫設定
    kb = config.get("knowledge_base", {})
    table.add_row("知識庫路徑", kb.get("path", "未設定"))

    # 機構記憶設定
    org = config.get("organizational_memory", {})
    table.add_row("機構記憶", "啟用" if org.get("enabled") else "停用")

    # 可用的 Provider 列表
    providers = config.get("providers", {})
    if providers:
        provider_list = ", ".join(providers.keys())
        table.add_row("已設定提供者", provider_list)

    console.print(table)
    console.print(f"\n[dim]設定檔位置：{cm.config_path.absolute()}[/dim]")


@app.command(name="validate")
def config_validate(
    config_path: str = typer.Option("config.yaml", "--path", "-p", help="設定檔路徑"),
) -> None:
    """
    驗證設定檔的格式與必要欄位。

    檢查項目：檔案是否存在、YAML 格式是否正確、必要欄位是否齊全。

    範例：

        gov-ai config validate

        gov-ai config validate --path my_config.yaml
    """
    # 1. 檢查檔案是否存在
    if not os.path.isfile(config_path):
        console.print(f"[red]找不到設定檔：{config_path}[/red]")
        raise typer.Exit(1)

    # 2. 嘗試解析 YAML
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        console.print(f"[red]設定檔格式錯誤：{e}[/red]")
        raise typer.Exit(1)

    if not isinstance(data, dict):
        data = {}

    # 3. 檢查必要欄位
    missing: list[str] = []
    llm_section = data.get("llm")
    if not isinstance(llm_section, dict):
        missing.append("llm")
        missing.append("llm.provider")
        missing.append("llm.model")
    else:
        if not llm_section.get("provider"):
            missing.append("llm.provider")
        if not llm_section.get("model"):
            missing.append("llm.model")

    if missing:
        console.print(f"[red]缺少必要欄位：{', '.join(missing)}[/red]")
        console.print("[red]設定檔驗證失敗[/red]")
        raise typer.Exit(1)

    console.print("[green]設定檔驗證通過[/green]")


@app.command()
def fetch_models(
    update: bool = typer.Option(False, "--update", "-u", help="以找到的最佳模型更新 config.yaml"),
    limit: int = typer.Option(5, "--limit", "-l", help="測試並顯示的模型數量", min=1, max=50),
    test: bool = typer.Option(True, "--test/--no-test", help="是否測試模型連線能力")
) -> None:
    """
    從 OpenRouter API 擷取、列出並測試最佳免費模型。

    範例：

        gov-ai config fetch-models                列出並測試前 5 名免費模型

        gov-ai config fetch-models -u             找到可用模型後自動更新 config.yaml

        gov-ai config fetch-models -l 10 --no-test  列出前 10 名但不測試連線
    """
    console.print("[cyan]正在從 OpenRouter 擷取模型清單...[/cyan]")

    # Load Config to get API Key
    cm = ConfigManager()
    # Try to find OpenRouter API Key
    # It could be in providers.openrouter.api_key or directly in env
    api_key = cm.config.get("providers", {}).get("openrouter", {}).get("api_key", "")

    # If api_key is still a template string (unexpanded),
    # try to get from env manually if ConfigManager didn't expand it yet?
    # ConfigManager expands on load. So if it's "", check env directly just in case.
    if not api_key:
        api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")

    try:
        response = requests.get("https://openrouter.ai/api/v1/models", timeout=15)
        response.raise_for_status()
        data = response.json()
        all_models = data.get("data", [])
    except requests.Timeout:
        console.print("[red]擷取模型清單逾時（15 秒），請確認網路連線後再試。[/red]")
        raise typer.Exit(1)
    except requests.ConnectionError:
        console.print("[red]無法連線至 OpenRouter API，請確認網路連線。[/red]")
        raise typer.Exit(1)
    except Exception as e:
        logger.debug("擷取模型清單失敗: %s", e)
        console.print("[red]擷取模型清單失敗，請稍後再試。[/red]")
        raise typer.Exit(1)

    # Filter for free models
    free_models = []
    for m in all_models:
        pricing = m.get("pricing", {})
        try:
            prompt_price = float(pricing.get("prompt", -1))
            completion_price = float(pricing.get("completion", -1))
            if prompt_price == 0 and completion_price == 0:
                free_models.append(m)
        except ValueError:
            continue

    # Sort by context length (descending)
    free_models.sort(key=lambda x: x.get("context_length", 0), reverse=True)

    # 顯示結果
    table = Table(title=f"前 {limit} 名免費模型（上下文長度 + 連線測試）")
    table.add_column("狀態", justify="center")
    table.add_column("ID", style="green")
    table.add_column("名稱", style="cyan")
    table.add_column("上下文長度", justify="right")

    candidate_models = free_models[:limit]
    best_working_model = None

    with console.status("[bold green]正在測試連線...[/bold green]") as status:
        for m in candidate_models:
            status_icon = "[gray]?[/gray]"

            if test and api_key:
                status.update(f"正在測試 {m['id']}...")
                if test_connectivity(m['id'], api_key):
                    status_icon = "[bold green]✅[/bold green]"
                    if not best_working_model:
                        best_working_model = m["id"]
                else:
                    status_icon = "[bold red]❌[/bold red]"

            table.add_row(
                status_icon,
                m["id"],
                m.get("name", "N/A"),
                str(m.get("context_length", "N/A"))
            )

    console.print(table)

    if test and not api_key:
        console.print("[yellow]警告：找不到 API Key，已跳過連線測試。[/yellow]")
        # 無法測試時，退回使用清單中第一個模型
        if not best_working_model and candidate_models:
            best_working_model = candidate_models[0]["id"]

    if not best_working_model and candidate_models:
        console.print("[yellow]沒有模型通過連線測試，退回使用清單中第一個模型。[/yellow]")
        best_working_model = candidate_models[0]["id"]

    if update and best_working_model:
        if Confirm.ask(f"是否將 config.yaml 中 OpenRouter 模型更新為 [bold green]{best_working_model}[/bold green]？"):
            # Same save logic as before
            with open(cm.config_path, 'r', encoding='utf-8') as f:
                raw_config = yaml.safe_load(f) or {}

            if "providers" not in raw_config:
                raw_config["providers"] = {}
            if "openrouter" not in raw_config["providers"]:
                raw_config["providers"]["openrouter"] = {}

            raw_config["providers"]["openrouter"]["model"] = best_working_model

            atomic_yaml_write(str(cm.config_path), raw_config)

            console.print("[green]設定檔更新成功！[/green]")


_PROVIDER_TEMPLATES = {
    "ollama": {
        "provider": "ollama",
        "model": "llama3.1:8b",
        "base_url": "http://127.0.0.1:11434",
        "embedding_provider": "ollama",
        "embedding_model": "llama3.1:8b",
        "embedding_base_url": "http://127.0.0.1:11434",
        "api_key": "",
    },
    "gemini": {
        "provider": "gemini",
        "model": "gemini-2.5-pro",
        "api_key": "${GEMINI_API_KEY}",
    },
    "openrouter": {
        "provider": "openrouter",
        "model": "${LLM_MODEL}",
        "api_key": "${LLM_API_KEY}",
        "base_url": "https://openrouter.ai/api/v1",
    },
}


@app.command()
def init() -> None:
    """
    互動式引導建立 config.yaml 設定檔。

    適合首次使用者快速完成設定。

    範例：

        gov-ai config init
    """
    config_path = "config.yaml"
    if os.path.isfile(config_path):
        if not Confirm.ask(
            f"[yellow]{config_path} 已存在，是否覆蓋？[/yellow]", default=False
        ):
            console.print("已取消。")
            raise typer.Exit()

    console.print(Panel(
        "[bold cyan]公文 AI 助理 — 設定檔建立引導[/bold cyan]\n\n"
        "此引導將協助您建立 config.yaml 設定檔。",
        border_style="cyan",
    ))

    # 1. 選擇 LLM 提供者
    console.print("\n[bold]1. 選擇 LLM 提供者[/bold]")
    console.print("  [dim]1) ollama  — 本機部署（免費，需安裝 Ollama）[/dim]")
    console.print("  [dim]2) gemini  — Google Gemini API（需 API Key）[/dim]")
    console.print("  [dim]3) openrouter — OpenRouter 聚合 API（需 API Key）[/dim]")

    choice = Prompt.ask("請選擇", choices=["1", "2", "3"], default="1")
    provider_map = {"1": "ollama", "2": "gemini", "3": "openrouter"}
    provider = provider_map[choice]
    llm_config = dict(_PROVIDER_TEMPLATES[provider])

    # 2. 如需要 API Key，引導設定
    if provider in ("gemini", "openrouter"):
        console.print("\n[bold]2. 設定 API Key[/bold]")
        if provider == "gemini":
            console.print("  [dim]請至 https://aistudio.google.com/apikey 取得 API Key[/dim]")
            env_var = "GEMINI_API_KEY"
        else:
            console.print("  [dim]請至 https://openrouter.ai/keys 取得 API Key[/dim]")
            env_var = "LLM_API_KEY"

        current = os.environ.get(env_var, "")
        if current:
            console.print(f"  [green]✓ 已偵測到環境變數 {env_var}[/green]")
        else:
            console.print(f"  [yellow]⚠ 環境變數 {env_var} 未設定[/yellow]")
            console.print(f"  [dim]請執行：export {env_var}=your-api-key[/dim]")
    else:
        console.print("\n[bold]2. Ollama 設定[/bold]")
        console.print("  [dim]請確認 Ollama 已安裝並啟動：ollama serve[/dim]")
        model = Prompt.ask("  模型名稱", default="llama3.1:8b")
        llm_config["model"] = model
        llm_config["embedding_model"] = model

    # 3. 知識庫路徑
    console.print("\n[bold]3. 知識庫路徑[/bold]")
    kb_path = Prompt.ask("  知識庫儲存路徑", default="./kb_data")

    # 4. 產生設定檔
    config_data = {
        "llm": llm_config,
        "knowledge_base": {"path": kb_path},
        "api": {"auth_enabled": True, "api_keys": []},
        "organizational_memory": {"enabled": True, "storage_path": f"{kb_path}/agency_preferences.json"},
    }

    atomic_yaml_write(str(config_path), config_data)

    console.print(f"\n[bold green]✓ 設定檔已建立：{config_path}[/bold green]")
    console.print("\n[bold]下一步：[/bold]")
    console.print("  [cyan]gov-ai quickstart[/cyan]  驗證環境")
    console.print("  [cyan]gov-ai generate -i \"台北市環保局發給各學校，加強資源回收\"[/cyan]  產生公文")


def _parse_value(value: str) -> None:
    """自動判斷值的類型：布林、整數、浮點數或字串。"""
    if value.lower() in ("true", "yes"):
        return True
    if value.lower() in ("false", "no"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


@app.command(name="set")
def set_value(
    key: str = typer.Argument(help="設定鍵（支援點號分隔路徑，例如 llm.temperature）"),
    value: str = typer.Argument(help="設定值（自動判斷數字、布林、字串）"),
) -> None:
    """設定 config.yaml 中的值。

    支援點號分隔的路徑，例如：llm.temperature, llm.max_tokens

    範例：

        gov-ai config set llm.temperature 0.7

        gov-ai config set llm.max_tokens 2048

        gov-ai config set llm.provider gemini
    """
    cm = ConfigManager()
    try:
        with open(cm.config_path, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f) or {}
    except Exception as e:
        console.print(f"[red]載入設定檔失敗：{e}[/red]")
        raise typer.Exit(1)

    keys = key.split(".")
    parsed_value = _parse_value(value)

    # 取得修改前的值
    node = raw_config
    for k in keys:
        if isinstance(node, dict):
            node = node.get(k)
        else:
            node = None
            break
    old_value = node

    # 遞迴設定值
    node = raw_config
    for k in keys[:-1]:
        if k not in node or not isinstance(node.get(k), dict):
            node[k] = {}
        node = node[k]
    node[keys[-1]] = parsed_value

    atomic_yaml_write(str(cm.config_path), raw_config)

    console.print(f"[cyan]{key}[/cyan]: [red]{old_value}[/red] → [green]{parsed_value}[/green]")


def _mask_sensitive(data, _sensitive_keys=("api_key", "secret", "token", "password")) -> None:
    """遞迴遮蔽敏感欄位。"""
    if isinstance(data, dict):
        return {
            k: "***" if any(sk in k.lower() for sk in _sensitive_keys) else _mask_sensitive(v)
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [_mask_sensitive(item) for item in data]
    return data


@app.command()
def export(
    output: str = typer.Option("", "-o", "--output", help="匯出檔案路徑（預設標準輸出）"),
    format: str = typer.Option("json", "--format", "-f", help="匯出格式：json / yaml"),
) -> None:
    """匯出目前設定。"""
    try:
        cm = ConfigManager()
        config = cm.config
    except Exception as e:
        console.print(f"[red]錯誤：無法讀取設定：{e}[/red]")
        raise typer.Exit(1)

    # 遮蔽敏感資訊
    masked = _mask_sensitive(config)

    if format.lower() == "yaml":
        result_text = yaml.dump(masked, allow_unicode=True, default_flow_style=False)
    else:
        result_text = json.dumps(masked, ensure_ascii=False, indent=2)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(result_text)
        console.print(f"[green]已匯出設定至：{output}[/green]")
    else:
        console.print(result_text)


@app.command(name="backup")
def config_backup(
    output: str = typer.Option("", "-o", "--output", help="備份檔案路徑"),
) -> None:
    """備份目前的設定檔。"""
    import shutil
    cm = ConfigManager()
    src_path = str(cm.config_path)

    if not os.path.isfile(src_path):
        console.print("[red]找不到設定檔。[/red]")
        raise typer.Exit(1)

    if output:
        dst_path = output
    else:
        dst_path = src_path + ".backup"

    shutil.copy2(src_path, dst_path)
    console.print(f"[green]已備份設定檔至：{dst_path}[/green]")
