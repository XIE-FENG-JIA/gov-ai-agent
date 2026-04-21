import os
import shutil


def show_impl(*, format_name, section, console, config_manager_cls):
    if format_name not in ("yaml", "json"):
        console.print(f"[red]不支援的格式：{format_name}（請使用 yaml 或 json）[/red]")
        raise ValueError("unsupported-format")

    cm = config_manager_cls()
    config = cm.config

    if section:
        sec_val = section.lower().strip()
        if sec_val in config:
            section_data = {sec_val: config[sec_val]}
            if format_name == "json":
                import json

                console.print(json.dumps(section_data, ensure_ascii=False, indent=2))
            else:
                console.print(f"\n[bold cyan]{sec_val} 設定區段：[/bold cyan]")
                items = config[sec_val] if isinstance(config[sec_val], dict) else {}
                for key, value in items.items():
                    console.print(f"  {key}: {value}")
            console.print(f"\n  [dim]區段篩選：{sec_val}[/dim]")
            return
        console.print(f"[yellow]找不到區段：{section}（可用：{', '.join(config.keys())}）[/yellow]")
        raise KeyError(section)

    if format_name == "json":
        import json

        console.print(json.dumps(config, ensure_ascii=False, indent=2))
        return

    from rich.table import Table

    table = Table(title="目前組態設定", show_lines=True)
    table.add_column("設定項", style="cyan", no_wrap=True)
    table.add_column("值", style="green")

    llm = config.get("llm", {})
    table.add_row("LLM 提供者", llm.get("provider", "未設定"))
    table.add_row("LLM 模型", llm.get("model", "未設定"))
    table.add_row("LLM Base URL", llm.get("base_url", "未設定"))
    api_key = llm.get("api_key", "")
    masked = "****" + api_key[-4:] if api_key and len(api_key) > 4 else "（未設定）"
    table.add_row("API Key", masked)
    table.add_row("Embedding 提供者", llm.get("embedding_provider", "未設定"))
    table.add_row("Embedding 模型", llm.get("embedding_model", "未設定"))
    table.add_row("Embedding Base URL", llm.get("embedding_base_url", "未設定"))

    kb = config.get("knowledge_base", {})
    table.add_row("知識庫路徑", kb.get("path", "未設定"))

    org = config.get("organizational_memory", {})
    table.add_row("機構記憶", "啟用" if org.get("enabled") else "停用")

    providers = config.get("providers", {})
    if providers:
        table.add_row("已設定提供者", ", ".join(providers.keys()))

    console.print(table)
    console.print(f"\n[dim]設定檔位置：{cm.config_path.absolute()}[/dim]")


def validate_impl(*, config_path, console, yaml_module):
    if not os.path.isfile(config_path):
        console.print(f"[red]找不到設定檔：{config_path}[/red]")
        raise FileNotFoundError(config_path)

    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            data = yaml_module.safe_load(handle)
    except yaml_module.YAMLError:
        raise

    if not isinstance(data, dict):
        data = {}

    missing = []
    llm_section = data.get("llm")
    if not isinstance(llm_section, dict):
        missing.extend(["llm", "llm.provider", "llm.model"])
    else:
        if not llm_section.get("provider"):
            missing.append("llm.provider")
        if not llm_section.get("model"):
            missing.append("llm.model")

    if missing:
        console.print(f"[red]缺少必要欄位：{', '.join(missing)}[/red]")
        console.print("[red]設定檔驗證失敗[/red]")
        raise ValueError("missing-fields")

    console.print("[green]設定檔驗證通過[/green]")


def init_impl(
    *,
    console,
    confirm_cls,
    prompt_cls,
    atomic_yaml_write_fn,
    provider_templates,
    environ,
):
    config_path = "config.yaml"
    if os.path.isfile(config_path):
        if not confirm_cls.ask(f"[yellow]{config_path} 已存在，是否覆蓋？[/yellow]", default=False):
            console.print("已取消。")
            raise RuntimeError("cancelled")

    from rich.panel import Panel

    console.print(
        Panel(
            "[bold cyan]公文 AI 助理 — 設定檔建立引導[/bold cyan]\n\n"
            "此引導將協助您建立 config.yaml 設定檔。",
            border_style="cyan",
        )
    )

    console.print("\n[bold]1. 選擇 LLM 提供者[/bold]")
    console.print("  [dim]1) ollama  — 本機部署（免費，需安裝 Ollama）[/dim]")
    console.print("  [dim]2) gemini  — Google Gemini API（需 API Key）[/dim]")
    console.print("  [dim]3) openrouter — OpenRouter 聚合 API（需 API Key）[/dim]")
    console.print("  [dim]4) minimax — MiniMax API（需 API Key）[/dim]")

    choice = prompt_cls.ask("請選擇", choices=["1", "2", "3", "4"], default="1")
    provider_map = {"1": "ollama", "2": "gemini", "3": "openrouter", "4": "minimax"}
    provider = provider_map[choice]
    llm_config = dict(provider_templates[provider])

    if provider in ("gemini", "openrouter", "minimax"):
        console.print("\n[bold]2. 設定 API Key[/bold]")
        if provider == "gemini":
            console.print("  [dim]請至 https://aistudio.google.com/apikey 取得 API Key[/dim]")
            env_var = "GEMINI_API_KEY"
        elif provider == "openrouter":
            console.print("  [dim]請至 https://openrouter.ai/keys 取得 API Key[/dim]")
            env_var = "LLM_API_KEY"
        else:
            console.print("  [dim]請至 MiniMax 開放平台取得 API Key[/dim]")
            env_var = "MINIMAX_API_KEY"

        current = environ.get(env_var, "")
        if current:
            console.print(f"  [green]✓ 已偵測到環境變數 {env_var}[/green]")
        else:
            console.print(f"  [yellow]⚠ 環境變數 {env_var} 未設定[/yellow]")
            console.print(f"  [dim]請執行：export {env_var}=your-api-key[/dim]")
    else:
        console.print("\n[bold]2. Ollama 設定[/bold]")
        console.print("  [dim]請確認 Ollama 已安裝並啟動：ollama serve[/dim]")
        model = prompt_cls.ask("  模型名稱", default="llama3.1:8b")
        llm_config["model"] = model
        llm_config["embedding_model"] = model

    console.print("\n[bold]3. 知識庫路徑[/bold]")
    kb_path = prompt_cls.ask("  知識庫儲存路徑", default="./kb_data")

    config_data = {
        "llm": llm_config,
        "knowledge_base": {"path": kb_path},
        "api": {"auth_enabled": True, "api_keys": []},
        "organizational_memory": {"enabled": True, "storage_path": f"{kb_path}/agency_preferences.json"},
    }
    atomic_yaml_write_fn(config_path, config_data)

    console.print(f"\n[bold green]✓ 設定檔已建立：{config_path}[/bold green]")
    console.print("\n[bold]下一步：[/bold]")
    console.print("  [cyan]gov-ai quickstart[/cyan]  驗證環境")
    console.print("  [cyan]gov-ai generate -i \"台北市環保局發給各學校，加強資源回收\"[/cyan]  產生公文")


def set_value_impl(
    *,
    key,
    value,
    console,
    config_manager_cls,
    yaml_module,
    parse_value_fn,
    safe_config_write_fn,
):
    cm = config_manager_cls()
    with open(cm.config_path, "r", encoding="utf-8") as handle:
        raw_config = yaml_module.safe_load(handle) or {}

    keys = key.split(".")
    parsed_value = parse_value_fn(value)

    node = raw_config
    for part in keys:
        if isinstance(node, dict):
            node = node.get(part)
        else:
            node = None
            break
    old_value = node

    node = raw_config
    for part in keys[:-1]:
        if part not in node or not isinstance(node.get(part), dict):
            node[part] = {}
        node = node[part]
    node[keys[-1]] = parsed_value

    safe_config_write_fn(str(cm.config_path), raw_config)
    console.print(f"[cyan]{key}[/cyan]: [red]{old_value}[/red] → [green]{parsed_value}[/green]")


def export_impl(
    *,
    output,
    format_name,
    console,
    config_manager_cls,
    mask_sensitive_fn,
    yaml_module,
):
    cm = config_manager_cls()
    masked = mask_sensitive_fn(cm.config)

    if format_name.lower() == "yaml":
        import_text = yaml_module.dump(masked, allow_unicode=True, default_flow_style=False)
    else:
        import json

        import_text = json.dumps(masked, ensure_ascii=False, indent=2)

    if output:
        with open(output, "w", encoding="utf-8") as handle:
            handle.write(import_text)
        console.print(f"[green]已匯出設定至：{output}[/green]")
        return

    console.print(import_text)


def backup_impl(*, output, console, config_manager_cls):
    cm = config_manager_cls()
    src_path = str(cm.config_path)

    if not os.path.isfile(src_path):
        console.print("[red]找不到設定檔。[/red]")
        raise FileNotFoundError(src_path)

    dst_path = output or src_path + ".backup"
    shutil.copy2(src_path, dst_path)
    console.print(f"[green]已備份設定檔至：{dst_path}[/green]")


def restore_impl(*, source, console, config_manager_cls, yaml_module, confirm_cls):
    cm = config_manager_cls()
    dst_path = str(cm.config_path)
    bak_path = source or dst_path + ".bak"

    if not os.path.isfile(bak_path):
        console.print(f"[red]找不到備份檔案：{bak_path}[/red]")
        console.print("[dim]提示：shrink guard 備份為 .bak，手動備份為 .backup[/dim]")
        raise FileNotFoundError(bak_path)

    try:
        with open(bak_path, "r", encoding="utf-8") as handle:
            bak_data = yaml_module.safe_load(handle) or {}
        keys = list(bak_data.keys()) if isinstance(bak_data, dict) else []
        console.print(f"[cyan]備份檔案包含 {len(keys)} 個 top-level key：{', '.join(keys)}[/cyan]")
    except Exception:
        pass

    if not confirm_cls.ask(f"確定要用 [bold]{bak_path}[/bold] 覆蓋目前的設定檔？"):
        console.print("[dim]已取消。[/dim]")
        raise RuntimeError("cancelled")

    shutil.copy2(bak_path, dst_path)
    console.print(f"[green]已從 {bak_path} 還原設定檔。[/green]")
