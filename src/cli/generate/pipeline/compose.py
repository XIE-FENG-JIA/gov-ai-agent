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
