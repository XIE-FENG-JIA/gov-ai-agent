import importlib


def _runtime():
    return importlib.import_module("src.cli.generate")


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
