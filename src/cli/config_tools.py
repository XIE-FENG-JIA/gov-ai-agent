import json
import logging
import os
import requests
import typer
import yaml
from rich.console import Console
from rich.prompt import Confirm, Prompt
from src.cli.utils_io import atomic_yaml_write, safe_config_write
from src.cli.config_tools_fetch_impl import fetch_models_impl
from src.cli.config_tools_mutations_impl import (
    backup_impl,
    export_impl,
    init_impl,
    restore_impl,
    set_value_impl,
    show_impl,
    validate_impl,
)
from src.core.config import ConfigManager
from src.core.llm import LiteLLMProvider

logger = logging.getLogger(__name__)
_CONFIG_TOOL_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError, Exception)

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
    except _CONFIG_TOOL_EXCEPTIONS as exc:
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
    try:
        show_impl(format_name=format, section=section, console=console, config_manager_cls=ConfigManager)
    except (ValueError, KeyError):
        raise typer.Exit(1)


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
    try:
        validate_impl(config_path=config_path, console=console, yaml_module=yaml)
    except yaml.YAMLError as e:
        console.print(f"[red]設定檔格式錯誤：{e}[/red]")
        raise typer.Exit(1)
    except (FileNotFoundError, ValueError):
        raise typer.Exit(1)


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
    try:
        fetch_models_impl(
            update=update,
            limit=limit,
            test=test,
            console=console,
            logger=logger,
            config_manager_cls=ConfigManager,
            requests_module=requests,
            confirm_cls=Confirm,
            yaml_module=yaml,
            safe_config_write_fn=safe_config_write,
            test_connectivity_fn=test_connectivity,
        )
    except (requests.Timeout, requests.ConnectionError, Exception):
        raise typer.Exit(1)


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
    "minimax": {
        "provider": "minimax",
        "model": "openai/MiniMax-M2.7",
        "api_key": "${MINIMAX_API_KEY}",
        "base_url": "https://api.minimax.io/v1",
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
    try:
        init_impl(
            console=console,
            confirm_cls=Confirm,
            prompt_cls=Prompt,
            atomic_yaml_write_fn=atomic_yaml_write,
            provider_templates=_PROVIDER_TEMPLATES,
            environ=os.environ,
        )
    except RuntimeError:
        raise typer.Exit()


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
    try:
        set_value_impl(
            key=key,
            value=value,
            console=console,
            config_manager_cls=ConfigManager,
            yaml_module=yaml,
            parse_value_fn=_parse_value,
            safe_config_write_fn=safe_config_write,
        )
    except _CONFIG_TOOL_EXCEPTIONS as e:
        console.print(f"[red]載入設定檔失敗：{e}[/red]")
        raise typer.Exit(1)


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
        export_impl(
            output=output,
            format_name=format,
            console=console,
            config_manager_cls=ConfigManager,
            mask_sensitive_fn=_mask_sensitive,
            yaml_module=yaml,
        )
    except _CONFIG_TOOL_EXCEPTIONS as e:
        console.print(f"[red]錯誤：無法讀取設定：{e}[/red]")
        raise typer.Exit(1)


@app.command(name="backup")
def config_backup(
    output: str = typer.Option("", "-o", "--output", help="備份檔案路徑"),
) -> None:
    """備份目前的設定檔。"""
    try:
        backup_impl(output=output, console=console, config_manager_cls=ConfigManager)
    except FileNotFoundError:
        raise typer.Exit(1)


@app.command(name="restore")
def config_restore(
    source: str = typer.Option("", "-s", "--source", help="備份檔案路徑（預設 config.yaml.bak）"),
) -> None:
    """從備份還原設定檔。

    shrink guard 自動產生的 .bak 備份，或手動 backup 產生的 .backup 備份，
    都可以用此命令還原。

    範例：

        gov-ai config restore                      從 config.yaml.bak 還原

        gov-ai config restore -s config.yaml.backup  從指定備份還原
    """
    try:
        restore_impl(
            source=source,
            console=console,
            config_manager_cls=ConfigManager,
            yaml_module=yaml,
            confirm_cls=Confirm,
        )
    except FileNotFoundError:
        raise typer.Exit(1)
    except RuntimeError:
        raise typer.Exit(0)
