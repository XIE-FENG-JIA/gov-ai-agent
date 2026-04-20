import importlib


def _runtime():
    return importlib.import_module("src.cli.generate")


def _sanitize_error(exc: Exception, max_len: int = 120) -> str:
    """將例外訊息截斷並移除可能的檔案系統路徑。"""
    runtime = _runtime()
    msg = runtime._PATH_PATTERN.sub("<path>", str(exc))
    if len(msg) > max_len:
        msg = msg[:max_len] + "..."
    return msg


def _resolve_generation_engine(llm) -> str:
    model_name = str(getattr(llm, "model_name", "") or "").strip()
    if model_name:
        return model_name

    provider = str(getattr(llm, "provider", "") or "").strip()
    model = str(getattr(llm, "model", "") or "").strip()
    if provider and model:
        return f"{provider}/{model}"
    if model:
        return model
    return provider


def _read_interactive_input() -> str:
    """從 stdin 管道或互動式提示取得使用者輸入。"""
    runtime = _runtime()
    console = runtime.console
    if not runtime.sys.stdin.isatty():
        piped = runtime.sys.stdin.read().strip()
        if piped:
            console.print(f"[dim]從 stdin 讀取到 {len(piped)} 字的需求描述。[/dim]")
            return piped

    console.print("[bold cyan]公文需求描述[/bold cyan]")
    console.print("[dim]請輸入您的公文需求（至少 5 字），包含發文者、受文者和主旨。[/dim]")
    console.print('[dim]範例：台北市環保局發給各學校，加強資源回收[/dim]')
    console.print("[dim]輸入空白行結束，按 Ctrl+C 取消。[/dim]\n")

    lines = []
    try:
        while True:
            line = console.input("[green]> [/green]")
            if not line and lines:
                break
            if line:
                lines.append(line)
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]已取消。[/yellow]")
        return ""

    result = "\n".join(lines).strip()
    if not result:
        console.print("[red]錯誤：未輸入任何內容。[/red]")
        return ""

    return result


def _load_batch_csv(batch_file: str) -> list[dict]:
    """讀取 CSV 批次檔案，欄位須包含 input，output 為選填。"""
    runtime = _runtime()
    with open(batch_file, "r", encoding="utf-8-sig") as handle:
        reader = runtime.csv.DictReader(handle)
        if reader.fieldnames is None or "input" not in reader.fieldnames:
            runtime.console.print("[red]錯誤：CSV 檔案必須包含 input 欄位。[/red]")
            runtime.console.print("[dim]格式：input,output[/dim]")
            raise runtime.typer.Exit(1)
        items = []
        for row in reader:
            if not row.get("input", "").strip():
                continue
            items.append({"input": row["input"], "output": row.get("output", "").strip() or None})
        return items


def _process_batch_item(
    item: dict,
    idx: int,
    total: int,
    llm,
    kb,
    skip_review: bool,
    max_rounds: int,
    convergence: bool,
    skip_info: bool,
    progress,
    task,
    parallel: bool = False,
) -> dict:
    """處理單一批次項目，回傳 {"success": bool, "failed_item": dict|None, "elapsed": float}。"""
    runtime = _runtime()
    item_start = runtime.time.monotonic()
    input_text = item["input"]
    output_path = item.get("output", f"batch_output_{idx}.docx")

    if not parallel:
        progress.console.rule(f"[bold cyan][{idx}/{total}] 正在處理...[/bold cyan]")
        progress.console.print(f"  需求：{input_text[:60]}{'...' if len(input_text) > 60 else ''}")

    result: dict = {"success": False, "failed_item": None, "elapsed": 0.0}

    try:
        req_agent = runtime.RequirementAgent(llm)
        if not parallel:
            progress.update(task, description=f"[{idx}/{total}] 分析需求中...")
        requirement = req_agent.analyze(input_text)

        writer = runtime.WriterAgent(llm, kb)
        if not parallel:
            progress.update(task, description=f"[{idx}/{total}] 撰寫草稿中...")
        raw_draft = writer.write_draft(requirement)

        template_engine = runtime.TemplateEngine()
        sections = template_engine.parse_draft(raw_draft)
        formatted_draft = template_engine.apply_template(requirement, sections)

        final_draft = formatted_draft
        qa_report_str = None
        if not skip_review:
            with runtime.EditorInChief(llm, kb) as editor:
                final_draft, qa_report = editor.review_and_refine(
                    formatted_draft,
                    requirement.doc_type,
                    max_rounds=max_rounds,
                    convergence=convergence,
                    skip_info=skip_info,
                )
                qa_report_str = qa_report.audit_log

        safe_filename = runtime.os.path.basename(output_path)
        if not safe_filename or safe_filename.startswith("."):
            safe_filename = f"batch_output_{idx}.docx"
        if not safe_filename.endswith(".docx"):
            safe_filename += ".docx"

        exporter = runtime.DocxExporter()
        final_path = exporter.export(final_draft, safe_filename, qa_report=qa_report_str)
        progress.console.print(f"  [green][{idx}/{total}] 完成 -> {final_path}[/green]")
        result["success"] = True

    except Exception as exc:
        analysis = runtime.ErrorAnalyzer.diagnose(exc)
        progress.console.print(f"  [red][{idx}/{total}] 失敗：{runtime._sanitize_error(exc)}[/red]")
        progress.console.print(f"  [dim]診斷：{analysis['root_cause']}[/dim]")
        progress.console.print(f"  [dim]建議：{analysis['suggestion']}[/dim]")
        failed_item = dict(item)
        failed_item["error_type"] = analysis["error_type"]
        failed_item["suggestion"] = analysis["suggestion"]
        result["failed_item"] = failed_item

    result["elapsed"] = runtime.time.monotonic() - item_start
    progress.advance(task)
    return result


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
    except Exception as exc:
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


def _retry_with_backoff(fn, retries: int, step_name: str):
    """帶指數退避的重試包裝器。"""
    runtime = _runtime()
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                wait = min(2 ** attempt, 10)
                runtime.console.print(
                    f"  [yellow]第 {attempt} 次嘗試失敗，{wait} 秒後重試（{runtime._sanitize_error(exc, 60)}）...[/yellow]"
                )
                runtime.time.sleep(wait)
    runtime.console.print(f"[red]{step_name}失敗（已重試 {retries} 次）：{runtime._sanitize_error(last_exc)}[/red]")
    analysis = runtime.ErrorAnalyzer.diagnose(last_exc)
    runtime.console.print(f"  [dim]診斷：{analysis['root_cause']}[/dim]")
    runtime.console.print(f"  [dim]建議：{analysis['suggestion']}[/dim]")
    raise runtime.typer.Exit(1)


def _resolve_input(input_text: str | None, from_file: str) -> str:
    """從 --input、--from-file 或互動式提示解析並驗證輸入。"""
    runtime = _runtime()
    if from_file:
        if input_text is not None:
            runtime.console.print("[red]錯誤：不可同時使用 --input 和 --from-file。[/red]")
            raise runtime.typer.Exit(1)
        if not runtime.os.path.isfile(from_file):
            runtime.console.print(f"[red]錯誤：找不到檔案：{from_file}[/red]")
            raise runtime.typer.Exit(1)
        try:
            with open(from_file, "r", encoding="utf-8-sig") as handle:
                input_text = handle.read().strip()
        except UnicodeDecodeError:
            runtime.console.print("[red]錯誤：檔案編碼不支援，請使用 UTF-8 編碼。[/red]")
            raise runtime.typer.Exit(1)
        except OSError as exc:
            runtime.console.print(f"[red]錯誤：無法讀取檔案：{runtime._sanitize_error(exc)}[/red]")
            raise runtime.typer.Exit(1)
        if not input_text:
            runtime.console.print("[red]錯誤：檔案內容為空。[/red]")
            raise runtime.typer.Exit(1)
        runtime.console.print(f"[dim]從檔案讀取到 {len(input_text)} 字的需求描述。[/dim]")

    if input_text is None:
        input_text = runtime._read_interactive_input()
        if not input_text:
            raise runtime.typer.Exit(1)
    elif not input_text.strip():
        runtime.console.print("[red]錯誤：公文需求描述不可為空白。[/red]")
        raise runtime.typer.Exit(1)

    stripped = input_text.strip()
    if len(stripped) < runtime._INPUT_MIN_LENGTH:
        runtime.console.print(
            f"[red]錯誤：需求描述至少需要 {runtime._INPUT_MIN_LENGTH} 個字（目前 {len(stripped)} 字）。[/red]"
        )
        runtime.console.print("[dim]提示：請提供更完整的公文需求，包含發文者、受文者和主旨。[/dim]")
        raise runtime.typer.Exit(1)
    if len(stripped) > runtime._INPUT_MAX_LENGTH:
        runtime.console.print(
            f"[red]錯誤：需求描述不可超過 {runtime._INPUT_MAX_LENGTH} 字（目前 {len(stripped)} 字）。[/red]"
        )
        runtime.console.print("[dim]提示：請精簡您的需求描述，僅保留核心資訊。[/dim]")
        raise runtime.typer.Exit(1)
    return input_text


def _init_pipeline(input_text: str, *, auto_sender: bool):
    """初始化 config、LLM、KB 並執行連線檢查。回傳 (config, llm, kb, input_text)。"""
    runtime = _runtime()
    config_manager = runtime.ConfigManager()
    config = config_manager.config
    llm_config = config.get("llm")
    if not llm_config:
        runtime.console.print("[red]錯誤：設定檔缺少 'llm' 區塊，請檢查 config.yaml[/red]")
        raise runtime.typer.Exit(1)

    if auto_sender:
        default_sender = config.get("default_sender", "")
        if default_sender:
            input_text = f"發文者：{default_sender}。{input_text}"
            runtime.console.print(f"  [dim]已自動填入發文者：{default_sender}[/dim]")
        else:
            runtime.console.print("[yellow]提示：config.yaml 未設定 default_sender，--auto-sender 無效。[/yellow]")
            runtime.console.print("[dim]請在 config.yaml 加入 default_sender: \"您的機關名稱\"[/dim]")

    kb_path = config.get("knowledge_base", {}).get("path", "./kb_data")
    llm = runtime.get_llm_factory(llm_config, full_config=config)
    kb = runtime.KnowledgeBaseManager(kb_path, llm)

    try:
        kb_stats = kb.get_stats()
        if kb_stats.get("examples_count", 0) == 0:
            runtime.console.print("[yellow]提示：知識庫尚未初始化，建議先執行 `gov-ai kb ingest` 匯入範例。[/yellow]")
            runtime.console.print("[dim]系統仍可繼續產生公文，但品質可能受限。[/dim]")
    except Exception as exc:
        runtime.console.print(f"[dim]知識庫檢查時發生例外：{exc}[/dim]")

    if isinstance(llm, runtime.LiteLLMProvider):
        with runtime.Status("[cyan]正在檢查 LLM 連線...[/cyan]", console=runtime.console):
            ok, err_msg = llm.check_connectivity(timeout=5)
        if not ok:
            runtime.console.print(f"[red]錯誤：{err_msg}[/red]")
            provider = llm_config.get("provider", "")
            if provider == "ollama":
                runtime.console.print("[dim]Ollama 用戶請確認已啟動：ollama serve[/dim]")
            elif provider in ("openrouter", "gemini"):
                runtime.console.print("[dim]API 用戶請確認 API Key 已設定：export LLM_API_KEY=your-key[/dim]")
            raise runtime.typer.Exit(1)

    return config, llm, kb, input_text


def _handle_dry_run(
    llm_config: dict,
    kb_path: str,
    input_text: str,
    output_path: str,
    *,
    skip_review: bool,
    convergence: bool,
    max_rounds: int,
) -> None:
    """Dry-run 模式：驗證配置後顯示結果。"""
    runtime = _runtime()
    runtime.console.rule("[bold blue]Dry Run 模式[/bold blue]")
    runtime.console.print("  [green]✓[/green] 設定檔載入成功")
    runtime.console.print(f"  [green]✓[/green] LLM 供應商：{llm_config.get('provider', '未設定')}")
    runtime.console.print(f"  [green]✓[/green] 模型：{llm_config.get('model', '未設定')}")
    runtime.console.print(f"  [green]✓[/green] 知識庫路徑：{kb_path}")
    runtime.console.print(f"  [green]✓[/green] 輸入長度：{len(input_text)} 字")
    runtime.console.print(f"  [green]✓[/green] 輸出路徑：{output_path}")
    if convergence:
        review_label = "啟用（分層收斂模式，零錯誤制）"
    elif skip_review:
        review_label = "跳過"
    else:
        review_label = f"啟用（最多 {max_rounds} 輪）"
    runtime.console.print(f"  [green]✓[/green] 審查：{review_label}")
    runtime.console.print("\n[bold green]Dry run 完成，一切就緒。[/bold green]")
    runtime.console.print("[dim]移除 --dry-run 即可正式生成公文。[/dim]")


def _handle_estimate(
    input_text: str,
    *,
    skip_review: bool,
    convergence: bool,
    max_rounds: int,
) -> None:
    """預估 LLM 使用量和耗時。"""
    runtime = _runtime()
    runtime.console.rule("[bold blue]LLM 使用量預估[/bold blue]")
    input_chars = len(input_text)
    input_tokens = input_chars * 2
    output_tokens = 2000
    review_tokens = 0
    if not skip_review:
        if convergence:
            est_rounds = 9
            review_tokens = est_rounds * 5 * 500
            output_tokens += est_rounds * 1000
        else:
            est_rounds = max_rounds
            review_tokens = est_rounds * 5 * 500
            output_tokens += 1000
    total_tokens = input_tokens + output_tokens + review_tokens
    est_time_min = total_tokens / 1000 * 2
    est_time_max = total_tokens / 1000 * 5
    runtime.console.print(f"  輸入長度：{input_chars} 字（≈ {input_tokens:,} tokens）")
    runtime.console.print(f"  預估輸出：≈ {output_tokens:,} tokens")
    if not skip_review:
        if convergence:
            runtime.console.print(f"  審查預估：≈ {review_tokens:,} tokens（分層收斂模式，最多 ~{est_rounds} 輪估算）")
        else:
            runtime.console.print(f"  審查預估：≈ {review_tokens:,} tokens（{max_rounds} 輪 × 5 agents）")
    runtime.console.print(f"  [bold]預估總量：≈ {total_tokens:,} tokens[/bold]")
    runtime.console.print(f"  預估耗時：{est_time_min:.0f} ~ {est_time_max:.0f} 秒")
    runtime.console.print("\n[dim]以上為粗略估算，實際用量因模型和內容而異。[/dim]")
    runtime.console.print("[dim]移除 --estimate 即可正式生成公文。[/dim]")


def _run_core_pipeline(
    llm,
    kb,
    input_text: str,
    *,
    skip_review: bool,
    max_rounds: int,
    convergence: bool,
    skip_info: bool,
    show_rounds: bool,
    retries: int,
    save_versions: bool,
    output_path: str,
    template_name: str,
) -> tuple:
    """執行核心 pipeline：需求分析→草稿撰寫→格式標準化→多 Agent 審查。"""
    runtime = _runtime()
    runtime.console.rule("[bold blue]步驟 1/5 · 需求分析[/bold blue]")
    req_agent = runtime.RequirementAgent(llm)

    def _do_analyze():
        with runtime.Status("[cyan]正在分析需求...[/cyan]", console=runtime.console):
            return req_agent.analyze(input_text)

    requirement = runtime._retry_with_backoff(_do_analyze, retries, "需求分析")
    runtime.console.print(f"  [green]類型：[/green]{requirement.doc_type}")
    runtime.console.print(f"  [green]主旨：[/green]{requirement.subject}")
    runtime.console.print(f"  [green]發文者：[/green]{requirement.sender}")
    runtime.console.print(f"  [green]受文者：[/green]{requirement.receiver}")

    runtime.console.rule("[bold blue]步驟 2/5 · 草稿撰寫 (RAG)[/bold blue]")
    writer = runtime.WriterAgent(llm, kb)

    def _do_write():
        with runtime.Status("[cyan]正在檢索範例並撰寫草稿...[/cyan]", console=runtime.console):
            return writer.write_draft(requirement)

    raw_draft = runtime._retry_with_backoff(_do_write, retries, "草稿撰寫")
    ver_num = 0
    if save_versions:
        ver_num += 1
        runtime._save_version(raw_draft, output_path, ver_num, "原始草稿")

    runtime.console.rule("[bold blue]步驟 3/5 · 格式標準化[/bold blue]")
    template_engine = runtime.TemplateEngine()
    try:
        sections = template_engine.parse_draft(raw_draft)
        formatted_draft = template_engine.apply_template(requirement, sections)
    except Exception as exc:
        runtime.console.print(f"[red]格式標準化失敗：{runtime._sanitize_error(exc)}[/red]")
        raise runtime.typer.Exit(1)
    runtime.console.print("  [green]格式標準化完成。[/green]")
    if template_name:
        runtime.console.print(f"  [dim]使用範本：{template_name}[/dim]")
    if save_versions:
        ver_num += 1
        runtime._save_version(formatted_draft, output_path, ver_num, "格式標準化")

    final_draft = formatted_draft
    qa_report = None
    qa_report_str = None
    if not skip_review:
        runtime.console.rule("[bold blue]步驟 4/5 · 多 Agent 審查[/bold blue]")
        with runtime.EditorInChief(llm, kb) as editor:
            final_draft, qa_report = editor.review_and_refine(
                formatted_draft,
                requirement.doc_type,
                max_rounds=max_rounds,
                convergence=convergence,
                skip_info=skip_info,
                show_rounds=show_rounds,
            )
            qa_report_str = qa_report.audit_log
        if save_versions:
            ver_num += 1
            runtime._save_version(final_draft, output_path, ver_num, "審查修正後")
    else:
        runtime.console.rule("[bold blue]步驟 4/5 · 審查（已跳過）[/bold blue]")
        runtime.console.print("  [yellow]已跳過多 Agent 審查步驟。[/yellow]")

    return requirement, final_draft, qa_report, qa_report_str, ver_num, _do_write, template_engine, writer


def _handle_confirm(
    final_draft: str,
    *,
    do_write_fn,
    retries: int,
    template_engine,
    requirement,
    skip_review: bool,
    llm,
    kb,
    max_rounds: int,
    convergence: bool,
    skip_info: bool,
    show_rounds: bool,
) -> tuple:
    """互動式確認迴圈。回傳 (final_draft, qa_report, qa_report_str)。"""
    runtime = _runtime()
    qa_report = None
    qa_report_str = None
    runtime.console.print()
    runtime.console.print(
        runtime.Panel(
            runtime.Markdown(final_draft[:500] + ("\n..." if len(final_draft) > 500 else "")),
            title="[bold cyan]草稿預覽[/bold cyan]",
            border_style="cyan",
        )
    )
    while True:
        choice = input("\n接受此草稿？(y=接受/r=重新生成/n=取消) ").strip().lower()
        if choice in ("y", "yes", ""):
            break
        if choice in ("r", "retry"):
            runtime.console.print("[yellow]重新生成...[/yellow]")
            raw_draft = runtime._retry_with_backoff(do_write_fn, retries, "草稿撰寫")
            sections = template_engine.parse_draft(raw_draft)
            formatted_draft = template_engine.apply_template(requirement, sections)
            final_draft = formatted_draft
            if not skip_review:
                with runtime.EditorInChief(llm, kb) as editor:
                    final_draft, qa_report = editor.review_and_refine(
                        formatted_draft,
                        requirement.doc_type,
                        max_rounds=max_rounds,
                        convergence=convergence,
                        skip_info=skip_info,
                        show_rounds=show_rounds,
                    )
                    qa_report_str = qa_report.audit_log
            runtime.console.print(
                runtime.Panel(
                    runtime.Markdown(final_draft[:500] + ("\n..." if len(final_draft) > 500 else "")),
                    title="[bold cyan]新草稿預覽[/bold cyan]",
                    border_style="cyan",
                )
            )
        elif choice in ("n", "no"):
            runtime.console.print("[yellow]已取消。[/yellow]")
            raise runtime.typer.Exit()
        else:
            runtime.console.print("[dim]請輸入 y（接受）、r（重新生成）或 n（取消）[/dim]")
    return final_draft, qa_report, qa_report_str
