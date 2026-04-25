"""
workflow package 的核心執行邏輯。
"""

import os
import re
from importlib import import_module
from typing import Any

from ._graph_report import _GraphQAReport
from ._ralph_loop import _count_report_issues, _is_ralph_goal_met, _run_ralph_loop


def _workflow_package():
    return import_module(__package__)


def _execute_document_workflow(
    user_input: str,
    llm,
    kb,
    session_id: str,
    skip_review: bool = False,
    max_rounds: int = 3,
    output_docx: bool = False,
    output_filename_hint: str | None = None,
    convergence: bool = False,
    skip_info: bool = False,
    ralph_loop: bool = False,
    ralph_max_cycles: int = 2,
    ralph_target_score: float = 1.0,
) -> tuple:
    """共用的公文生成工作流程（同步，需在執行緒池中呼叫）。"""
    workflow = _workflow_package()
    if ralph_loop:
        if skip_review:
            workflow.logger.info("RALPH loop 啟用時忽略 skip_review=True，改為強制審查")
        skip_review = False

    req_agent = workflow.RequirementAgent(llm)
    requirement = req_agent.analyze(user_input)

    writing_hints = ""
    org_mem = workflow.get_org_memory()
    if org_mem and requirement.sender:
        writing_hints = org_mem.get_writing_hints(requirement.sender)

    writer = workflow.WriterAgent(llm, kb)
    if writing_hints:
        original_reason = requirement.reason or ""
        requirement.reason = (f"{original_reason}\n\n" f"【機構寫作偏好】\n{writing_hints}").strip()
    raw_draft = writer.write_draft(requirement)

    template_engine = workflow.TemplateEngine()
    sections = template_engine.parse_draft(raw_draft)
    formatted_draft = template_engine.apply_template(requirement, sections)

    final_draft = formatted_draft
    qa_report = None
    rounds_used = 0

    if not skip_review:
        with workflow.EditorInChief(llm, kb) as editor:
            if ralph_loop:
                final_draft, qa_report, rounds_used = workflow._run_ralph_loop(
                    editor,
                    final_draft,
                    requirement.doc_type,
                    max_rounds=max_rounds,
                    max_cycles=ralph_max_cycles,
                    target_score=ralph_target_score,
                )
            else:
                final_draft, qa_report = editor.review_and_refine(
                    final_draft,
                    requirement.doc_type,
                    max_rounds=max_rounds,
                    convergence=convergence,
                    skip_info=skip_info,
                    show_rounds=False,
                )
                rounds_used = qa_report.rounds_used

    final_draft = writer.normalize_existing_draft(final_draft)
    final_sections = template_engine.parse_draft(final_draft)
    final_draft = template_engine.apply_template(requirement, final_sections)
    final_draft = writer.normalize_existing_draft(final_draft)

    force_post_verify = os.environ.get("API_FORCE_POST_REVIEW_VERIFY", "0") == "1"
    agent_results = getattr(qa_report, "agent_results", None) if qa_report else None
    has_agent_results = isinstance(agent_results, list) and len(agent_results) > 0
    if (ralph_loop or force_post_verify) and (not skip_review) and qa_report is not None and has_agent_results:
        with workflow.EditorInChief(llm, kb) as verifier:
            results, timed_out = verifier._execute_review(final_draft, requirement.doc_type)
            verified_report = verifier._generate_qa_report(results, timed_out)

        verified_report.rounds_used = rounds_used
        previous_history = getattr(qa_report, "iteration_history", None)
        if previous_history:
            verified_report.iteration_history = previous_history

        previous_audit_log = str(getattr(qa_report, "audit_log", "") or "")
        trace_match = re.search(r"\n## Ralph Loop Trace[\s\S]*$", previous_audit_log)
        if trace_match and "## Ralph Loop Trace" not in (verified_report.audit_log or ""):
            verified_report.audit_log = f"{verified_report.audit_log.rstrip()}\n" + trace_match.group(0)

        original_score = float(getattr(qa_report, "overall_score", 0.0) or 0.0)
        verified_score = float(getattr(verified_report, "overall_score", 0.0) or 0.0)
        if verified_score >= original_score:
            qa_report = verified_report

    output_filename = None
    if output_docx:
        exporter = workflow.DocxExporter()
        filename = workflow._sanitize_output_filename(output_filename_hint, session_id)
        os.makedirs(workflow.OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(workflow.OUTPUT_DIR, filename)
        exporter.export(
            final_draft,
            output_path,
            qa_report=qa_report.audit_log if qa_report else None,
        )
        output_filename = filename

    return requirement, final_draft, qa_report, output_filename, rounds_used


def _execute_via_graph(
    user_input: str,
    session_id: str,
    skip_review: bool = False,
    max_rounds: int = 3,
    output_docx: bool = False,
    output_filename_hint: str | None = None,
    convergence: bool = False,
    skip_info: bool = False,
    **_: Any,
) -> tuple:
    """透過 LangGraph 執行公文生成流程。"""
    workflow = _workflow_package()
    graph = workflow._get_graph()

    initial_state = {
        "user_input": user_input,
        "review_requested": not skip_review,
        "max_refinement_rounds": max_rounds,
        "refinement_round": 0,
        "review_results": [],
        "phase": "init",
    }
    final_state = graph.invoke(initial_state)

    graph_error = final_state.get("error")
    if graph_error:
        workflow.logger.warning("LangGraph 流程出現錯誤: %s", graph_error)

    requirement_dict = final_state.get("requirement") or {}
    if not requirement_dict:
        raise ValueError(f"LangGraph 需求分析失敗: {graph_error or '未知原因'}")
    requirement = workflow.PublicDocRequirement(**requirement_dict)

    final_draft = final_state.get("refined_draft") or final_state.get("formatted_draft") or final_state.get("draft") or ""
    if not final_draft.strip():
        workflow.logger.warning(
            "LangGraph 草稿為空 (phase=%s, error=%s)",
            final_state.get("phase"),
            graph_error,
        )

    aggregated = final_state.get("aggregated_report")
    report_md = final_state.get("report", "")
    rounds_used = final_state.get("refinement_round", 0)

    qa_report = None
    if aggregated and not skip_review:
        qa_report = workflow._GraphQAReport(
            overall_score=aggregated.get("overall_score", 0.0),
            risk_summary=aggregated.get("risk_summary", "Unknown"),
            error_count=aggregated.get("error_count", 0),
            warning_count=aggregated.get("warning_count", 0),
            agent_results=aggregated.get("agent_results", []),
            rounds_used=rounds_used,
            report_markdown=report_md,
            audit_log=report_md,
        )

    graph_output = final_state.get("output_path")
    if graph_output and os.path.isfile(graph_output):
        try:
            os.remove(graph_output)
            workflow.logger.debug("已清理 graph 臨時匯出檔: %s", graph_output)
        except OSError:
            pass

    output_filename = None
    if output_docx:
        exporter = workflow.DocxExporter()
        filename = workflow._sanitize_output_filename(output_filename_hint, session_id)
        os.makedirs(workflow.OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(workflow.OUTPUT_DIR, filename)
        exporter.export(
            final_draft,
            output_path,
            qa_report=qa_report.audit_log if qa_report else None,
        )
        output_filename = filename

    return requirement, final_draft, qa_report, output_filename, rounds_used
