import typer
import requests
import yaml
import os
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm
from src.core.config import ConfigManager
from src.core.llm import LiteLLMProvider

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
    except Exception:
        return False

@app.command()
def fetch_models(
    update: bool = typer.Option(False, "--update", "-u", help="以找到的最佳模型更新 config.yaml"),
    limit: int = typer.Option(5, "--limit", "-l", help="測試並顯示的模型數量"),
    test: bool = typer.Option(True, "--test/--no-test", help="是否測試模型連線能力")
):
    """
    從 OpenRouter API 擷取、列出並測試最佳免費模型。
    """
    console.print("[cyan]正在從 OpenRouter 擷取模型清單...[/cyan]")
    
    # Load Config to get API Key
    cm = ConfigManager()
    # Try to find OpenRouter API Key
    # It could be in providers.openrouter.api_key or directly in env
    api_key = cm.config.get("providers", {}).get("openrouter", {}).get("api_key", "")
    
    # If api_key is still a template string (unexpanded), try to get from env manually if ConfigManager didn't expand it yet?
    # ConfigManager expands on load. So if it's "", check env directly just in case.
    if not api_key:
        api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")

    try:
        response = requests.get("https://openrouter.ai/api/v1/models")
        response.raise_for_status()
        data = response.json()
        all_models = data.get("data", [])
    except Exception as e:
        console.print(f"[red]擷取模型清單失敗：{e}[/red]")
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
                raw_config = yaml.safe_load(f)
            
            if "providers" not in raw_config:
                raw_config["providers"] = {}
            if "openrouter" not in raw_config["providers"]:
                raw_config["providers"]["openrouter"] = {}
            
            raw_config["providers"]["openrouter"]["model"] = best_working_model
            
            with open(cm.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(raw_config, f, default_flow_style=False, allow_unicode=True)
            
            console.print("[green]設定檔更新成功！[/green]")

