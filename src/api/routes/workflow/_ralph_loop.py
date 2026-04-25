"""Ralph Loop execution helpers for workflow routes."""

import os
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
