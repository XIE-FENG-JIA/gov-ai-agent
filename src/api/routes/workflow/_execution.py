"""
workflow package 的核心執行邏輯。
"""

import os
import re
import time
from importlib import import_module
from typing import Any


def _workflow_package():
    return import_module(__package__)


def _count_report_issues(qa_report: Any) -> int:
    """統計 QA 報告中的 issues 總數（相容 model 與 dict）。"""
    if qa_report is None:
        return 0

    total = 0
    for agent_result in getattr(qa_report, "agent_results", []) or []:
        if isinstance(agent_result, dict):
            total += len(agent_result.get("issues", []) or [])
            continue
        total += len(getattr(agent_result, "issues", []) or [])
    return total


def _is_ralph_goal_met(qa_report: Any, target_score: float) -> bool:
    """判斷 Ralph Loop 是否達成滿分門檻。"""
    if qa_report is None:
        return False

    score = float(getattr(qa_report, "overall_score", 0.0) or 0.0)
    risk = str(getattr(qa_report, "risk_summary", "") or "")
    return score >= target_score and risk == "Safe" and _count_report_issues(qa_report) == 0


def _run_ralph_loop(
    editor,
    draft: str,
    doc_type: str,
    max_rounds: int,
    max_cycles: int,
    target_score: float,
) -> tuple[str, Any, int]:
    """以極限品質模式反覆執行 convergence 迭代，直到達標或達上限。"""
    workflow = _workflow_package()
    current_draft = draft
    best_draft = draft
    total_rounds = 0
    final_report = None
    best_report = None
    best_score = -1.0
    best_issues = 10**9
    best_cycle = 0
    merged_history: list[dict[str, Any]] = []
    cycle_trace: list[dict[str, Any]] = []
    round_offset = 0
    prev_score: float | None = None
    prev_issues: int | None = None
    prev_risk: str | None = None

    loop_budget_sec = int(
        os.environ.get(
            "API_RALPH_LOOP_BUDGET_SEC",
            str(max(180, int(workflow.MEETING_TIMEOUT * 0.8))),
        )
    )
    min_cycle_remaining_sec = int(os.environ.get("API_RALPH_MIN_REMAINING_SEC", "240"))
    started = time.monotonic()

    for cycle in range(1, max_cycles + 1):
        elapsed = time.monotonic() - started
        if cycle > 1 and elapsed >= loop_budget_sec:
            workflow.logger.warning(
                "RALPH loop budget reached before cycle %d: elapsed=%.1fs budget=%ds",
                cycle,
                elapsed,
                loop_budget_sec,
            )
            break

        current_draft, cycle_report = editor.review_and_refine(
            current_draft,
            doc_type,
            max_rounds=max_rounds,
            convergence=False,
            skip_info=True,
            show_rounds=False,
        )
        final_report = cycle_report

        rounds = int(cycle_report.rounds_used or 0)
        total_rounds += rounds

        cycle_history = cycle_report.iteration_history or []
        for item in cycle_history:
            merged_item = dict(item)
            if isinstance(merged_item.get("round"), int):
                merged_item["round"] = merged_item["round"] + round_offset
            merged_item["ralph_cycle"] = cycle
            merged_history.append(merged_item)
        round_offset += rounds

        score = float(cycle_report.overall_score or 0.0)
        risk = str(cycle_report.risk_summary or "")
        issue_count = _count_report_issues(cycle_report)
        goal_met = _is_ralph_goal_met(cycle_report, target_score)
        if score > best_score or (score == best_score and issue_count < best_issues):
            best_score = score
            best_issues = issue_count
            best_draft = current_draft
            best_report = cycle_report
            best_cycle = cycle
        cycle_trace.append(
            {
                "cycle": cycle,
                "score": score,
                "risk": risk,
                "issues": issue_count,
                "rounds": rounds,
                "goal_met": goal_met,
            }
        )
        workflow.logger.info(
            "RALPH loop cycle %d/%d: score=%.2f, risk=%s, issues=%d, rounds=%d, goal_met=%s",
            cycle,
            max_cycles,
            score,
            risk,
            issue_count,
            rounds,
            goal_met,
        )
        if goal_met:
            break

        remaining = loop_budget_sec - (time.monotonic() - started)
        if cycle < max_cycles and remaining < min_cycle_remaining_sec:
            workflow.logger.warning(
                "RALPH loop early-stop: remaining=%.1fs < min_cycle_remaining=%ds",
                remaining,
                min_cycle_remaining_sec,
            )
            break

        if (
            prev_score is not None
            and prev_issues is not None
            and prev_risk is not None
            and score <= prev_score + 0.01
            and issue_count >= prev_issues
            and risk == prev_risk
        ):
            workflow.logger.info(
                "RALPH loop early-stop: stagnated (prev_score=%.2f, score=%.2f, prev_issues=%d, issues=%d, risk=%s)",
                prev_score,
                score,
                prev_issues,
                issue_count,
                risk,
            )
            break

        prev_score = score
        prev_issues = issue_count
        prev_risk = risk

    selected_report = best_report or final_report
    selected_draft = best_draft if best_report is not None else current_draft

    if selected_report is not None:
        selected_report.rounds_used = total_rounds
        if merged_history:
            selected_report.iteration_history = merged_history

        trace_lines = [
            "## Ralph Loop Trace",
            f"- target_score={target_score:.2f}",
            f"- max_cycles={max_cycles}",
            f"- goal_met={any(item['goal_met'] for item in cycle_trace)}",
            f"- best_cycle={best_cycle}",
        ]
        for item in cycle_trace:
            trace_lines.append(
                "- cycle {cycle}: score={score:.2f}, risk={risk}, issues={issues}, rounds={rounds}, goal_met={goal_met}".format(
                    **item
                )
            )
        selected_report.audit_log = f"{selected_report.audit_log.rstrip()}\n\n" + "\n".join(trace_lines)

    return selected_draft, selected_report, total_rounds


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


class _GraphQAReport:
    """輕量 QA 報告物件，模擬原始 QAReport 的 API 介面。"""

    def __init__(
        self,
        overall_score: float,
        risk_summary: str,
        error_count: int,
        warning_count: int,
        agent_results: list,
        rounds_used: int,
        report_markdown: str,
        audit_log: str,
    ):
        self.overall_score = overall_score
        self.risk_summary = risk_summary
        self.error_count = error_count
        self.warning_count = warning_count
        self.agent_results = agent_results
        self.rounds_used = rounds_used
        self.report_markdown = report_markdown
        self.audit_log = audit_log

    def model_dump(self) -> dict:
        """序列化為 dict，與 Pydantic QAReport.model_dump() 相容。"""
        return {
            "overall_score": self.overall_score,
            "risk_summary": self.risk_summary,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "agent_results": self.agent_results,
            "rounds_used": self.rounds_used,
            "report_markdown": self.report_markdown,
            "audit_log": self.audit_log,
        }
