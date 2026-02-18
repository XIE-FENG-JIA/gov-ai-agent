import typer
import yaml
from typing import Optional
from rich.console import Console
from rich.prompt import Prompt
from src.core.config import ConfigManager

console = Console()
app = typer.Typer()

@app.command()
def switch(
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="直接指定 LLM 提供者（例如：ollama、gemini、openrouter）")
):
    """
    互動式切換目前使用的 LLM 提供者。
    """
    cm = ConfigManager()
    
    # Load raw config to preserve structure when saving
    try:
        with open(cm.config_path, 'r', encoding='utf-8') as f:
            raw_config = yaml.safe_load(f)
    except Exception as e:
        console.print(f"[red]載入設定檔時發生錯誤：{e}[/red]")
        raise typer.Exit(1)

    current_provider = raw_config.get("llm", {}).get("provider", "ollama")
    available_providers = list(raw_config.get("providers", {}).keys())
    
    # Ensure ollama is always an option even if not in providers list explicitly
    if "ollama" not in available_providers:
        available_providers.append("ollama")

    if not provider:
        console.print(f"目前提供者：[bold green]{current_provider}[/bold green]")
        console.print("\n可用的提供者：")
        for i, p in enumerate(available_providers, 1):
            console.print(f"{i}. {p}")

        choice = Prompt.ask("\n請選擇提供者編號", choices=[str(i) for i in range(1, len(available_providers) + 1)])
        selected_provider = available_providers[int(choice) - 1]
    else:
        # 非互動模式
        if provider not in available_providers:
            console.print(f"[red]無效的提供者：{provider}[/red]")
            console.print(f"可用的提供者：{', '.join(available_providers)}")
            raise typer.Exit(1)
        selected_provider = provider

    if selected_provider == current_provider:
        console.print("[yellow]提供者未變更。[/yellow]")
        return

    # 更新設定
    if "llm" not in raw_config:
        raw_config["llm"] = {}
    
    raw_config["llm"]["provider"] = selected_provider

    # 將 LLM 區塊更新為所選提供者的預設值
    provider_defaults = raw_config.get("providers", {}).get(selected_provider, {})
    
    if "model" in provider_defaults:
        raw_config["llm"]["model"] = provider_defaults["model"]
    
    if "api_key" in raw_config["llm"]:
        raw_config["llm"]["api_key"] = ""  # 重設為空值（安全預設）
        
    if "base_url" in provider_defaults:
        raw_config["llm"]["base_url"] = provider_defaults["base_url"]
    elif "base_url" in raw_config["llm"]:
         raw_config["llm"]["base_url"] = ""

    # 儲存設定
    with open(cm.config_path, 'w', encoding='utf-8') as f:
        yaml.dump(raw_config, f, default_flow_style=False, allow_unicode=True)

    console.print(f"\n[bold green]已成功切換至：{selected_provider}[/bold green]")
    console.print(f"模型：{raw_config['llm'].get('model', '預設')}")
