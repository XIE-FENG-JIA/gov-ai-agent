import os


def fetch_models_impl(
    *,
    update,
    limit,
    test,
    console,
    logger,
    config_manager_cls,
    requests_module,
    confirm_cls,
    yaml_module,
    safe_config_write_fn,
    test_connectivity_fn,
):
    """Shared implementation for the config fetch-models command."""
    console.print("[cyan]正在從 OpenRouter 擷取模型清單...[/cyan]")

    cm = config_manager_cls()
    api_key = cm.config.get("providers", {}).get("openrouter", {}).get("api_key", "")
    if not api_key:
        api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")

    try:
        response = requests_module.get("https://openrouter.ai/api/v1/models", timeout=15)
        response.raise_for_status()
        data = response.json()
        all_models = data.get("data", [])
    except requests_module.Timeout:
        console.print("[red]擷取模型清單逾時（15 秒），請確認網路連線後再試。[/red]")
        raise
    except requests_module.ConnectionError:
        console.print("[red]無法連線至 OpenRouter API，請確認網路連線。[/red]")
        raise
    except (requests_module.HTTPError, ValueError) as exc:
        logger.debug("擷取模型清單失敗: %s", exc)
        console.print("[red]擷取模型清單失敗，請稍後再試。[/red]")
        raise

    free_models = []
    for model in all_models:
        pricing = model.get("pricing", {})
        try:
            prompt_price = float(pricing.get("prompt", -1))
            completion_price = float(pricing.get("completion", -1))
        except ValueError:
            continue
        if prompt_price == 0 and completion_price == 0:
            free_models.append(model)

    free_models.sort(key=lambda item: item.get("context_length", 0), reverse=True)

    table = requests_table(limit, console)
    candidate_models = free_models[:limit]
    best_working_model = None

    with console.status("[bold green]正在測試連線...[/bold green]") as status:
        for model in candidate_models:
            status_icon = "[gray]?[/gray]"

            if test and api_key:
                status.update(f"正在測試 {model['id']}...")
                if test_connectivity_fn(model["id"], api_key):
                    status_icon = "[bold green]✅[/bold green]"
                    if not best_working_model:
                        best_working_model = model["id"]
                else:
                    status_icon = "[bold red]❌[/bold red]"

            table.add_row(
                status_icon,
                model["id"],
                model.get("name", "N/A"),
                str(model.get("context_length", "N/A")),
            )

    console.print(table)

    if test and not api_key:
        console.print("[yellow]警告：找不到 API Key，已跳過連線測試。[/yellow]")
        if not best_working_model and candidate_models:
            best_working_model = candidate_models[0]["id"]

    if not best_working_model and candidate_models:
        console.print("[yellow]沒有模型通過連線測試，退回使用清單中第一個模型。[/yellow]")
        best_working_model = candidate_models[0]["id"]

    if update and best_working_model:
        message = (
            "是否將 config.yaml 中 OpenRouter 模型更新為 "
            f"[bold green]{best_working_model}[/bold green]？"
        )
        if confirm_cls.ask(message):
            with open(cm.config_path, "r", encoding="utf-8") as handle:
                raw_config = yaml_module.safe_load(handle) or {}

            raw_config.setdefault("providers", {})
            raw_config["providers"].setdefault("openrouter", {})
            raw_config["providers"]["openrouter"]["model"] = best_working_model

            safe_config_write_fn(str(cm.config_path), raw_config)
            console.print("[green]設定檔更新成功！[/green]")


def requests_table(limit, console):
    from rich.table import Table

    table = Table(title=f"前 {limit} 名免費模型（上下文長度 + 連線測試）")
    table.add_column("狀態", justify="center")
    table.add_column("ID", style="green")
    table.add_column("名稱", style="cyan")
    table.add_column("上下文長度", justify="right")
    return table
