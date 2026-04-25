import importlib

from .item_processor import _process_batch_item


def _runtime():
    return importlib.import_module("src.cli.generate")


def _run_batch(
    batch_file: str,
    skip_review: bool,
    max_rounds: int = 3,
    convergence: bool = False,
    skip_info: bool = False,
    workers: int = 1,
):
    """批次處理 JSON 或 CSV 檔案中的多筆公文需求。"""
    runtime = _runtime()
    if not runtime.os.path.isfile(batch_file):
        runtime.console.print(f"[red]錯誤：找不到批次檔案：{batch_file}[/red]")
        raise runtime.typer.Exit(1)

    is_csv = batch_file.lower().endswith(".csv")
    if is_csv:
        try:
            items = runtime._load_batch_csv(batch_file)
        except (UnicodeDecodeError, runtime.csv.Error) as exc:
            runtime.console.print(f"[red]錯誤：無法解析 CSV 檔案：{runtime._sanitize_error(exc)}[/red]")
            raise runtime.typer.Exit(1)
    else:
        try:
            with open(batch_file, "r", encoding="utf-8") as handle:
                items = runtime.json.load(handle)
        except (runtime.json.JSONDecodeError, UnicodeDecodeError) as exc:
            runtime.console.print(f"[red]錯誤：無法解析 JSON 檔案：{runtime._sanitize_error(exc)}[/red]")
            raise runtime.typer.Exit(1)

    if not isinstance(items, list) or not items:
        fmt = "CSV" if is_csv else "JSON"
        runtime.console.print(f"[red]錯誤：{fmt} 檔案必須包含至少一筆資料。[/red]")
        if not is_csv:
            runtime.console.print('[dim]格式：[{"input": "需求描述", "output": "輸出路徑"}, ...][/dim]')
        raise runtime.typer.Exit(1)

    for idx, item in enumerate(items):
        if not isinstance(item, dict) or "input" not in item:
            runtime.console.print(f'[red]錯誤：第 {idx + 1} 筆缺少 "input" 欄位。[/red]')
            raise runtime.typer.Exit(1)

    try:
        config_manager = runtime.ConfigManager()
        config = config_manager.config
        llm_config = config.get("llm")
        if not llm_config:
            runtime.console.print("[red]錯誤：設定檔缺少 'llm' 區塊[/red]")
            raise runtime.typer.Exit(1)
        kb_path = config.get("knowledge_base", {}).get("path", "./kb_data")
        llm = runtime.get_llm_factory(llm_config, full_config=config)
        kb = runtime.KnowledgeBaseManager(kb_path, llm)
    except runtime.typer.Exit:
        raise
    except (OSError, ValueError, RuntimeError, KeyError, ImportError) as exc:
        runtime.console.print(f"[red]錯誤：初始化失敗：{runtime._sanitize_error(exc)}[/red]")
        raise runtime.typer.Exit(1)

    total = len(items)
    workers = max(1, workers)
    success_count = 0
    fail_count = 0
    failed_items: list[dict] = []
    batch_start = runtime.time.monotonic()
    item_times: list[float] = []
    lock = runtime.threading.Lock()

    parallel = workers > 1
    mode_label = f"並行 {workers} workers" if parallel else "序列"
    runtime.console.rule(f"[bold blue]批次處理：共 {total} 筆（{mode_label}）[/bold blue]")

    with runtime.Progress(
        runtime.SpinnerColumn(),
        runtime.TextColumn("[progress.description]{task.description}"),
        runtime.BarColumn(),
        runtime.TaskProgressColumn(),
        runtime.TimeElapsedColumn(),
        console=runtime.console,
    ) as progress:
        task = progress.add_task("批次處理", total=total)

        def _collect(result: dict) -> None:
            nonlocal success_count, fail_count
            with lock:
                item_times.append(result["elapsed"])
                if result["success"]:
                    success_count += 1
                else:
                    fail_count += 1
                    if result["failed_item"]:
                        failed_items.append(result["failed_item"])

        if not parallel:
            for idx, item in enumerate(items, 1):
                result = runtime._process_batch_item(
                    item,
                    idx,
                    total,
                    llm,
                    kb,
                    skip_review,
                    max_rounds,
                    convergence,
                    skip_info,
                    progress,
                    task,
                    parallel=False,
                )
                _collect(result)
        else:
            with runtime.concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {
                    executor.submit(
                        runtime._process_batch_item,
                        item,
                        idx,
                        total,
                        llm,
                        kb,
                        skip_review,
                        max_rounds,
                        convergence,
                        skip_info,
                        progress,
                        task,
                        True,
                    ): idx
                    for idx, item in enumerate(items, 1)
                }
                for future in runtime.concurrent.futures.as_completed(future_map):
                    _collect(future.result())

    batch_elapsed = runtime.time.monotonic() - batch_start
    runtime.console.rule("[bold blue]批次處理統計[/bold blue]")
    runtime.console.print(f"  [green]成功：{success_count} 筆[/green]")
    if fail_count:
        runtime.console.print(f"  [red]失敗：{fail_count} 筆[/red]")
    runtime.console.print(f"  共計：{total} 筆")
    runtime.console.print(f"  總耗時：{batch_elapsed:.1f} 秒")
    if item_times:
        runtime.console.print(f"  平均每筆：{sum(item_times) / len(item_times):.1f} 秒")

    if failed_items:
        retry_file = runtime.os.path.splitext(batch_file)[0] + "_failed.json"
        try:
            runtime.atomic_json_write(retry_file, failed_items)
            runtime.console.print(f"  [yellow]失敗項目已儲存至：{retry_file}[/yellow]")
            runtime.console.print(f"  [dim]重試指令：gov-ai generate --batch {retry_file}[/dim]")
        except OSError:
            pass
