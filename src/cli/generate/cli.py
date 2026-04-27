import importlib

import typer


def _runtime():
    return importlib.import_module("src.cli.generate")


def generate(
    input_text: str | None = typer.Option(
        None,
        "--input",
        "-i",
        help="公文需求描述（自然語言，至少 5 字）",
    ),
    output_path: str = typer.Option(
        "output.docx",
        "--output",
        "-o",
        help="輸出 .docx 檔案的儲存路徑",
    ),
    skip_review: bool = typer.Option(False, help="跳過多 Agent 審查步驟"),
    max_rounds: int = typer.Option(3, "--max-rounds", help="最大審查輪數（經典模式 1-5）", min=1, max=5),
    convergence: bool = typer.Option(False, "--convergence", help="啟用分層收斂迭代（零錯誤制，自動迭代直到完美）"),
    skip_info: bool = typer.Option(False, "--skip-info", help="分層收斂模式下跳過 info 層級修正"),
    show_rounds: bool = typer.Option(False, "--show-rounds", help="每輪修正後顯示草稿全文與差異對比"),
    batch: str = typer.Option("", "--batch", "-b", help="批次處理檔案路徑（支援 .json 和 .csv）"),
    workers: int = typer.Option(1, "--workers", "-w", help="批次並行 worker 數（預設 1=序列，建議上限 5）", min=1, max=10),
    preview: bool = typer.Option(False, "--preview", "-p", help="在終端預覽生成的公文內容"),
    retries: int = typer.Option(1, "--retries", help="LLM 呼叫失敗時的重試次數（1=不重試）", min=1, max=5),
    save_markdown: bool = typer.Option(False, "--markdown", "--md", help="同時匯出 Markdown 版本"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="安靜模式，僅顯示最終結果"),
    confirm: bool = typer.Option(False, "--confirm", help="生成後確認是否接受（可選擇重試）"),
    export_report: str = typer.Option("", "--export-report", help="將 QA 審查報告匯出至指定路徑（支援 .json / .txt）"),
    save_versions: bool = typer.Option(False, "--save-versions", help="每輪修正自動保存草稿版本（供 compare 比較）"),
    from_file: str = typer.Option("", "--from-file", "-f", help="從文字檔讀取公文需求描述（.txt / .md）"),
    dry_run: bool = typer.Option(False, "--dry-run", help="模擬生成流程，不呼叫 LLM（用於驗證配置）"),
    lang_check: bool = typer.Option(False, "--lang-check", help="生成後檢查公文用語品質"),
    auto_sender: bool = typer.Option(False, "--auto-sender", help="從 config 自動填入發文者資訊"),
    estimate: bool = typer.Option(False, "--estimate", help="預估 LLM 使用量和耗時（不實際生成）"),
    summary: bool = typer.Option(False, "--summary", help="生成後顯示視覺化摘要卡片"),
    priority_tag: str = typer.Option("", "--priority-tag", help="優先標記（urgent=急件 / confidential=密 / normal=無）"),
    cc: str = typer.Option("", "--cc", help="副本收受者（逗號分隔，如 --cc '教育局,衛生局'）"),
    watermark: str = typer.Option("", "--watermark", help="浮水印文字（如 --watermark '草稿'）"),
    header: str = typer.Option("", "--header", help="自訂公文頁首（如 --header '台北市政府'）"),
    footnote: str = typer.Option("", "--footnote", help="附加註腳（如 --footnote '本案如有疑義請洽承辦人'）"),
    ref_number: str = typer.Option("", "--ref-number", help="自訂發文字號（如 --ref-number '北市環字第11200001號'）"),
    encoding: str = typer.Option("utf-8", "--encoding", help="Markdown 匯出編碼（utf-8/big5/utf-8-sig）"),
    date: str = typer.Option("", "--date", help="自訂發文日期（如 --date '114年3月9日'）"),
    sign: str = typer.Option("", "--sign", help="署名（如 --sign '局長 王小明'）"),
    attachment: str = typer.Option("", "--attachment", help="附件清單（逗號分隔，如 --attachment '實施計畫,經費概算表'）"),
    classification: str = typer.Option("", "--classification", help="公文密等（密/機密/極機密/限閱）"),
    template_name: str = typer.Option("", "--template-name", help="指定範本名稱（如 --template-name '正式函'）"),
    receiver_title: str = typer.Option("", "--receiver-title", help="受文者敬稱（如 --receiver-title '鈞鑒'）"),
    speed: str = typer.Option("normal", "--speed", help="生成速度模式（fast/normal/careful）"),
    page_break: bool = typer.Option(False, "--page-break", help="在說明與辦法之間插入分頁標記"),
    margin: str = typer.Option("standard", "--margin", help="頁邊距設定（standard/narrow/wide）"),
    line_spacing: str = typer.Option("1.5", "--line-spacing", help="行距設定（1.0/1.5/2.0）"),
    font_size: str = typer.Option("12", "--font-size", help="字型大小（10/12/14/16）"),
    duplex: str = typer.Option("off", "--duplex", help="雙面列印設定（off/long-edge/short-edge）"),
    orientation: str = typer.Option("portrait", "--orientation", help="紙張方向（portrait/landscape）"),
    paper_size: str = typer.Option("A4", "--paper-size", help="紙張大小（A4/B4/A3/Letter）"),
    columns: str = typer.Option("1", "--columns", help="排版欄數（1/2）"),
    seal: str = typer.Option("none", "--seal", help="用印設定（none/official/personal）"),
    copy_count: str = typer.Option("1", "--copy-count", help="輸出份數（1-10）"),
    draft_mark: str = typer.Option("none", "--draft-mark", help="草稿標記（none/draft/internal）"),
    urgency_label: str = typer.Option("normal", "--urgency-label", help="急件標示（normal/urgent/most-urgent）"),
    lang: str = typer.Option("zh-TW", "--lang", help="公文語言（zh-TW/zh-CN/en）"),
    header_logo: str = typer.Option("", "--header-logo", help="頁首 logo 圖片路徑"),
    disclaimer: str = typer.Option("", "--disclaimer", help="免責聲明文字"),
    cite: bool = typer.Option(True, "--cite/--no-cite", help="生成後自動顯示適用法規引用建議（預設開啟）"),
    lint: bool = typer.Option(True, "--lint/--no-lint", help="生成後自動執行輕量格式與用語 lint 檢查（預設開啟）"),
    output_format: str = typer.Option("text", "--format", help="輸出格式：text（預設）或 json"),
):
    """
    根據自然語言輸入產生完整的政府公文。

    支援 12 種公文類型：函、公告、簽、書函、令、開會通知單、
    呈、咨、會勘通知單、公務電話紀錄、手令、箋函。
    """
    import json as _json
    from rich.console import Console as _Console
    _console = _Console()
    if output_format not in {"text", "json"}:
        _console.print(f"[red]錯誤：不支援的輸出格式 '{output_format}'，請使用 text 或 json。[/red]")
        raise typer.Exit(1)

    runtime = _runtime()

    if batch:
        runtime._run_batch(
            batch,
            skip_review,
            max_rounds=max_rounds,
            convergence=convergence,
            skip_info=skip_info,
            workers=workers,
        )
        return

    input_text = runtime._resolve_input(input_text, from_file)
    config, llm, kb, input_text = runtime._init_pipeline(input_text, auto_sender=auto_sender)
    llm_config = config.get("llm")
    kb_path = config.get("knowledge_base", {}).get("path", "./kb_data")

    if dry_run:
        runtime._handle_dry_run(
            llm_config,
            kb_path,
            input_text,
            output_path,
            skip_review=skip_review,
            convergence=convergence,
            max_rounds=max_rounds,
        )
        return

    if estimate:
        runtime._handle_estimate(
            input_text,
            skip_review=skip_review,
            convergence=convergence,
            max_rounds=max_rounds,
        )
        return

    gen_start = runtime.time.monotonic()
    requirement, final_draft, qa_report, qa_report_str, _, do_write_fn, template_engine, writer = runtime._run_core_pipeline(
        llm,
        kb,
        input_text,
        skip_review=skip_review,
        max_rounds=max_rounds,
        convergence=convergence,
        skip_info=skip_info,
        show_rounds=show_rounds,
        retries=retries,
        save_versions=save_versions,
        output_path=output_path,
        template_name=template_name,
    )

    if confirm and runtime.sys.stdin.isatty():
        final_draft, new_qa, new_qa_str = runtime._handle_confirm(
            final_draft,
            do_write_fn=do_write_fn,
            retries=retries,
            template_engine=template_engine,
            requirement=requirement,
            skip_review=skip_review,
            llm=llm,
            kb=kb,
            max_rounds=max_rounds,
            convergence=convergence,
            skip_info=skip_info,
            show_rounds=show_rounds,
        )
        if new_qa is not None:
            qa_report = new_qa
        if new_qa_str is not None:
            qa_report_str = new_qa_str

    final_draft = runtime._apply_content_metadata(
        final_draft,
        priority_tag=priority_tag,
        cc=cc,
        receiver_title=receiver_title,
        ref_number=ref_number,
        date=date,
        header=header,
        classification=classification,
        watermark=watermark,
        footnote=footnote,
        sign=sign,
        attachment=attachment,
        page_break=page_break,
        disclaimer=disclaimer,
    )
    runtime._display_format_options(
        speed=speed,
        margin=margin,
        line_spacing=line_spacing,
        font_size=font_size,
        duplex=duplex,
        orientation=orientation,
        paper_size=paper_size,
        columns=columns,
        seal=seal,
        copy_count=copy_count,
        draft_mark=draft_mark,
        urgency_label=urgency_label,
        lang=lang,
        header_logo=header_logo,
    )

    full_output_path = runtime._export_document(
        final_draft,
        output_path,
        qa_report_str=qa_report_str,
        qa_report=qa_report,
        citation_metadata={
            "reviewed_sources": list(getattr(writer, "_last_sources_list", []) or []),
            "engine": runtime._resolve_generation_engine(llm),
            "ai_generated": True,
        },
        save_markdown=save_markdown,
        encoding=encoding,
        preview=preview,
        lang_check_flag=lang_check,
        export_report=export_report,
        requirement=requirement,
    )

    gen_elapsed = runtime.time.monotonic() - gen_start
    runtime._display_summary(requirement, qa_report, gen_elapsed, full_output_path, summary_flag=summary)

    if output_format == "json":
        print(_json.dumps({
            "output": full_output_path,
            "doc_type": requirement.doc_type if requirement else None,
            "score": float(qa_report.overall_score) if qa_report and qa_report.overall_score is not None else None,
            "elapsed_sec": round(gen_elapsed, 3),
        }, ensure_ascii=False))
        return

    if cite and not batch and not quiet:
        runtime._show_cite_suggestions(requirement.doc_type)
    if lint and not batch and not quiet:
        runtime._show_lint_results(final_draft)

    try:
        runtime.append_record(
            input_text=input_text,
            doc_type=requirement.doc_type,
            output_path=full_output_path,
            score=qa_report.overall_score if qa_report else None,
            risk=qa_report.risk_summary if qa_report else None,
            rounds_used=qa_report.rounds_used if qa_report else None,
            elapsed=gen_elapsed,
        )
    except (OSError, ValueError) as exc:
        runtime.console.print(f"[dim]歷史記錄寫入失敗：{exc}[/dim]")
