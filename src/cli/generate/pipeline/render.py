import importlib


def _runtime():
    return importlib.import_module("src.cli.generate")


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
    except (ValueError, TypeError, AttributeError, KeyError, RuntimeError) as exc:
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
