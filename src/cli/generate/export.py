import importlib
import logging


logger = logging.getLogger(__name__)

_EXPORT_DOCUMENT_EXCEPTIONS = (OSError, RuntimeError, ValueError)
_QA_REPORT_EXPORT_EXCEPTIONS = (OSError, TypeError, ValueError, RuntimeError)
_LINT_DISPLAY_EXCEPTIONS = (ImportError, AttributeError, OSError, RuntimeError, TypeError, ValueError)
_CITE_SUGGESTION_EXCEPTIONS = (ImportError, AttributeError, OSError, RuntimeError, TypeError, ValueError)

from .content_metadata import _apply_content_metadata, _display_format_options


def _runtime():
    return importlib.import_module("src.cli.generate")


def _export_document(
    final_draft: str,
    output_path: str,
    *,
    qa_report_str: str | None,
    qa_report,
    citation_metadata: dict | None,
    save_markdown: bool,
    encoding: str,
    preview: bool,
    lang_check_flag: bool,
    export_report: str,
    requirement,
) -> str:
    """匯出 DOCX、Markdown，並執行後處理檢查。回傳最終輸出路徑。"""
    runtime = _runtime()
    console = runtime.console
    console.rule("[bold blue]步驟 5/5 · 匯出文件[/bold blue]")

    has_traversal = ".." in output_path
    is_absolute = runtime.os.path.isabs(output_path) or output_path.startswith("/")
    safe_filename = runtime.os.path.basename(output_path)
    if not safe_filename or safe_filename.startswith("."):
        safe_filename = "output.docx"
    if not safe_filename.endswith(".docx"):
        safe_filename += ".docx"

    if is_absolute or has_traversal:
        full_output_path = safe_filename
    elif runtime.os.path.dirname(output_path):
        output_dir = runtime.os.path.dirname(runtime.os.path.abspath(output_path))
        full_output_path = runtime.os.path.join(output_dir, safe_filename)
    else:
        full_output_path = safe_filename

    exporter = runtime.DocxExporter()
    try:
        final_path = exporter.export(
            final_draft,
            full_output_path,
            qa_report=qa_report_str,
            citation_metadata=citation_metadata,
        )
        console.print(f"[bold green]完成！文件已儲存至：[/bold green] {final_path}")
    except _EXPORT_DOCUMENT_EXCEPTIONS as exc:
        logger.warning("DOCX 匯出失敗: %s", exc)
        console.print(f"[red]匯出失敗：{runtime._sanitize_error(exc)}[/red]")
        raise runtime.typer.Exit(1)

    if save_markdown:
        valid_encodings = {"utf-8", "big5", "utf-8-sig"}
        md_enc = encoding.lower().strip() if encoding else "utf-8"
        if md_enc not in valid_encodings:
            valid_list = ", ".join(sorted(valid_encodings))
            console.print(f"[yellow]不支援的編碼 '{encoding}'，改用 utf-8。可用：{valid_list}[/yellow]")
            md_enc = "utf-8"
        md_path = runtime.os.path.splitext(full_output_path)[0] + ".md"
        console.print(f"  [dim]Markdown 編碼：{md_enc}[/dim]")
        try:
            runtime.atomic_text_write(md_path, final_draft, encoding=md_enc)
            enc_note = f"（{md_enc}）" if md_enc != "utf-8" else ""
            console.print(f"  [green]Markdown 版本：{md_path}{enc_note}[/green]")
        except OSError as exc:
            console.print(f"  [yellow]Markdown 匯出失敗（{md_enc}）：{runtime._sanitize_error(exc)}[/yellow]")

    sc_findings = runtime.detect_simplified(final_draft)
    if sc_findings:
        unique_chars = sorted(set((s, t) for s, t, _ in sc_findings))
        console.print(f"\n[yellow]⚠ 偵測到 {len(sc_findings)} 處可能的簡體字：[/yellow]")
        for sc, tc in unique_chars[:10]:
            console.print(f"  [yellow]「{sc}」→ 建議「{tc}」[/yellow]")
        if len(unique_chars) > 10:
            console.print(f"  [dim]...及其他 {len(unique_chars) - 10} 種字[/dim]")
        console.print("[dim]提示：建議檢查並修正為繁體中文。[/dim]")

    if lang_check_flag:
        findings = runtime.check_language(final_draft)
        if findings:
            console.print(f"\n[yellow]公文用語檢查：發現 {len(findings)} 項建議[/yellow]")
            for finding in findings[:15]:
                label = "口語詞" if finding["type"] == "informal" else "贅詞"
                console.print(
                    f"  [{label}] 「{finding['found']}」→ 建議「{finding['suggest']}」（{finding['count']} 處）"
                )
        else:
            console.print("\n[green]公文用語檢查：未發現口語詞或贅詞。[/green]")

    if preview:
        console.print()
        console.print(
            runtime.Panel(
                runtime.Markdown(final_draft),
                title=f"[bold cyan]公文預覽 — {requirement.doc_type}[/bold cyan]",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    if export_report and qa_report:
        runtime._export_qa_report(qa_report, export_report)

    return full_output_path


def _save_version(content: str, output_path: str, version: int, label: str):
    """將草稿版本儲存至 <basename>_v<N>.md 檔案。"""
    runtime = _runtime()
    ver_path = f"{runtime.os.path.splitext(output_path)[0]}_v{version}.md"
    try:
        runtime.atomic_text_write(ver_path, content)
        runtime.console.print(f"  [dim]版本 {version}（{label}）已儲存：{ver_path}[/dim]")
    except OSError as exc:
        runtime.console.print(f"  [yellow]版本儲存失敗：{exc}[/yellow]")


def _export_qa_report(qa_report, report_path: str):
    """將 QA 審查報告匯出至指定路徑（.json 或 .txt）。"""
    runtime = _runtime()
    try:
        if report_path.endswith(".json"):
            report_data = {
                "overall_score": qa_report.overall_score,
                "risk_summary": qa_report.risk_summary,
                "rounds_used": qa_report.rounds_used,
                "iteration_history": qa_report.iteration_history,
                "agent_results": [
                    {
                        "agent": result.agent_name,
                        "score": result.score,
                        "confidence": result.confidence,
                        "issues_count": len(result.issues),
                        "issues": [
                            {"severity": issue.severity, "message": issue.message}
                            for issue in result.issues
                        ],
                    }
                    for result in qa_report.agent_results
                ],
                "audit_log": qa_report.audit_log,
            }
            runtime.atomic_json_write(report_path, report_data)
        else:
            runtime.atomic_text_write(report_path, qa_report.audit_log)
        runtime.console.print(f"  [green]QA 報告已匯出至：{report_path}[/green]")
    except _QA_REPORT_EXPORT_EXCEPTIONS as exc:
        logger.warning("QA 報告匯出失敗 (%s): %s", report_path, exc)
        runtime.console.print(f"  [yellow]QA 報告匯出失敗：{runtime._sanitize_error(exc)}[/yellow]")


def _show_lint_results(content: str) -> None:
    """生成完成後對草稿執行輕量 lint 檢查，以 Panel 顯示問題摘要（靜默降級）。"""
    runtime = _runtime()
    try:
        from src.cli._shared.lint_invocation import run_lint

        issues = run_lint(content)
        runtime.console.print()
        if not issues:
            runtime.console.print(
                runtime.Panel(
                    "[bold green]✓ 格式與用語檢查通過[/bold green]",
                    title="[bold]📝 Lint 檢查[/bold]",
                    border_style="dim green",
                    padding=(0, 2),
                )
            )
            return
        shown = issues[:5]
        lines = [
            f"  [yellow]{issue['category']}[/yellow]  "
            f"{'第 ' + str(issue['line']) + ' 行' if issue['line'] > 0 else '（全文）'} — {issue['detail']}"
            for issue in shown
        ]
        if len(issues) > 5:
            lines.append(f"  [dim]… 還有 {len(issues) - 5} 個問題，執行 gov-ai lint -f <草稿> 查看全部[/dim]")
        runtime.console.print(
            runtime.Panel(
                "\n".join(lines),
                title=f"[bold]📝 Lint 檢查（共 {len(issues)} 個問題）[/bold]",
                subtitle="[dim]完整審查：gov-ai lint -f <草稿檔案>[/dim]",
                border_style="dim yellow",
                padding=(0, 2),
            )
        )
    except _LINT_DISPLAY_EXCEPTIONS as exc:
        logger.warning("Lint 摘要顯示失敗: %s", exc)


def _show_cite_suggestions(doc_type: str) -> None:
    """生成完成後自動顯示適用法規引用建議（靜默降級）。"""
    runtime = _runtime()
    try:
        from src.cli._shared.citation_format import (
            MAPPING_PATH,
            filter_applicable_citations,
            load_citation_mapping,
        )

        regulations = load_citation_mapping(MAPPING_PATH)
        applicable = filter_applicable_citations(regulations, doc_type)
        if not applicable:
            return
        runtime.console.print()
        cite_lines = [f"  依據《{reg['name']}》" for reg in applicable[:5]]
        runtime.console.print(
            runtime.Panel(
                "\n".join(cite_lines),
                title=f"[bold]📋 適用法規引用建議（{doc_type}，共 {len(applicable)} 部）[/bold]",
                subtitle="[dim]完整建議：gov-ai cite <草稿檔案>[/dim]",
                border_style="dim cyan",
                padding=(0, 2),
            )
        )
    except _CITE_SUGGESTION_EXCEPTIONS as exc:
        logger.warning("引用建議顯示失敗（%s）: %s", doc_type, exc)


def _display_summary(
    requirement,
    qa_report,
    gen_elapsed: float,
    full_output_path: str,
    *,
    summary_flag: bool,
) -> None:
    """顯示摘要卡片或簡單統計。"""
    runtime = _runtime()
    console = runtime.console
    if summary_flag:
        score_str = f"{qa_report.overall_score:.2f}" if qa_report else "N/A"
        risk_str = qa_report.risk_summary if qa_report else "未審查"
        risk_colors = {
            "Safe": "green",
            "Low": "green",
            "Moderate": "yellow",
            "High": "red",
            "Critical": "red",
        }
        risk_color = risk_colors.get(risk_str, "white")
        card_lines = [
            f"[bold]{requirement.doc_type}[/bold]",
            f"主旨：{requirement.subject}",
            f"發文者：{requirement.sender} → 受文者：{requirement.receiver}",
            "",
            f"品質分數：[bold]{score_str}[/bold]  風險等級：[{risk_color}]{risk_str}[/{risk_color}]",
            f"處理時間：{gen_elapsed:.1f} 秒  輸出：{full_output_path}",
        ]
        console.print()
        console.print(
            runtime.Panel(
                "\n".join(card_lines),
                title="[bold cyan]公文生成摘要[/bold cyan]",
                border_style="cyan",
                padding=(1, 2),
            )
        )
    else:
        console.print("\n[bold]統計摘要[/bold]")
        console.print(f"  類型：{requirement.doc_type}  速別：{requirement.urgency}")
        console.print(f"  處理時間：{gen_elapsed:.1f} 秒")
        if qa_report:
            console.print(f"  品質分數：{qa_report.overall_score:.2f}  風險等級：{qa_report.risk_summary}")
            console.print(f"  審查輪數：{qa_report.rounds_used}")
