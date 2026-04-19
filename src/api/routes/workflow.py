"""
完整工作流程路由 — Meeting、檔案下載、批次處理
=============================================
"""

import asyncio
import logging
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from src.core.constants import SESSION_ID_LENGTH, OUTPUT_DIR
from src.core.models import PublicDocRequirement
from src.agents.editor import EditorInChief
from src.agents.requirement import RequirementAgent
from src.agents.writer import WriterAgent
from src.agents.template import TemplateEngine
from src.document.exporter import DocxExporter
from src.graph import build_graph

from src.api.dependencies import get_llm, get_kb, get_org_memory
from src.api.helpers import (
    _sanitize_error,
    _get_error_code,
    _sanitize_output_filename,
    run_in_executor,
    MEETING_TIMEOUT,
    BATCH_TOTAL_TIMEOUT,
)
from src.api.models import (
    MeetingRequest,
    MeetingResponse,
    BatchRequest,
    BatchItemResult,
    BatchResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# 批次處理並行度控制（模組級，避免每次請求重建）
_BATCH_SEMAPHORE = asyncio.Semaphore(3)

# LangGraph 單例（延遲初始化，雙重檢查鎖）
_GRAPH = None
_graph_lock = threading.Lock()

# 詳細審查報告快取（供 /api/v1/detailed-review 查詢）
_DETAILED_REVIEW_MAX_ITEMS = max(
    1,
    int(os.environ.get("API_DETAILED_REVIEW_MAX_ITEMS", "500")),
)
_DETAILED_REVIEW_STORE: dict[str, dict[str, Any]] = {}
_detailed_review_lock = threading.Lock()


def _cache_detailed_review(
    session_id: str,
    requirement: dict[str, Any],
    final_draft: str,
    qa_report: dict[str, Any] | None,
    rounds_used: int,
) -> None:
    """快取詳細審查報告（固定容量，超出時移除最舊項目）。"""
    if qa_report is None:
        return

    payload = {
        "success": True,
        "session_id": session_id,
        "requirement": requirement,
        "final_draft": final_draft,
        "qa_report": qa_report,
        "rounds_used": rounds_used,
    }

    with _detailed_review_lock:
        _DETAILED_REVIEW_STORE[session_id] = payload
        while len(_DETAILED_REVIEW_STORE) > _DETAILED_REVIEW_MAX_ITEMS:
            oldest_session_id = next(iter(_DETAILED_REVIEW_STORE))
            _DETAILED_REVIEW_STORE.pop(oldest_session_id, None)


def _get_cached_detailed_review(session_id: str) -> dict[str, Any] | None:
    """依 session_id 取得快取中的詳細審查報告。"""
    with _detailed_review_lock:
        payload = _DETAILED_REVIEW_STORE.get(session_id)
        if payload is None:
            return None
        # 回傳淺拷貝，避免呼叫端直接修改快取容器本身
        return dict(payload)


def _get_graph():
    """取得已編譯的 LangGraph 單例（thread-safe lazy init）。"""
    global _GRAPH
    if _GRAPH is not None:
        return _GRAPH
    with _graph_lock:
        if _GRAPH is None:
            logger.info("初始化 LangGraph 公文生成流程圖...")
            _GRAPH = build_graph()
            logger.info("LangGraph 流程圖初始化完成")
    return _GRAPH


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
    editor: EditorInChief,
    draft: str,
    doc_type: str,
    max_rounds: int,
    max_cycles: int,
    target_score: float,
) -> tuple[str, Any, int]:
    """以極限品質模式反覆執行 convergence 迭代，直到達標或達上限。"""
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

    # 防止單一請求在 RALPH 第二循環拖到 API timeout：保留時間給序列化與回傳
    loop_budget_sec = int(os.environ.get(
        "API_RALPH_LOOP_BUDGET_SEC",
        str(max(180, int(MEETING_TIMEOUT * 0.8))),
    ))
    min_cycle_remaining_sec = int(os.environ.get("API_RALPH_MIN_REMAINING_SEC", "240"))
    started = time.monotonic()

    for cycle in range(1, max_cycles + 1):
        elapsed = time.monotonic() - started
        if cycle > 1 and elapsed >= loop_budget_sec:
            logger.warning(
                "RALPH loop budget reached before cycle %d: elapsed=%.1fs budget=%ds",
                cycle, elapsed, loop_budget_sec,
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
        # 保留跨 cycle 的最佳版本，避免後續循環退化覆蓋高分結果。
        if score > best_score or (score == best_score and issue_count < best_issues):
            best_score = score
            best_issues = issue_count
            best_draft = current_draft
            best_report = cycle_report
            best_cycle = cycle
        cycle_trace.append({
            "cycle": cycle,
            "score": score,
            "risk": risk,
            "issues": issue_count,
            "rounds": rounds,
            "goal_met": goal_met,
        })
        logger.info(
            "RALPH loop cycle %d/%d: score=%.2f, risk=%s, issues=%d, rounds=%d, goal_met=%s",
            cycle, max_cycles, score, risk, issue_count, rounds, goal_met,
        )
        if goal_met:
            break

        # 早停條件 A：下一循環剩餘時間不足，避免請求逾時
        remaining = loop_budget_sec - (time.monotonic() - started)
        if cycle < max_cycles and remaining < min_cycle_remaining_sec:
            logger.warning(
                "RALPH loop early-stop: remaining=%.1fs < min_cycle_remaining=%ds",
                remaining, min_cycle_remaining_sec,
            )
            break

        # 早停條件 B：分數/issue/risk 幾乎無改善，避免無效長迭代
        if (
            prev_score is not None
            and prev_issues is not None
            and prev_risk is not None
            and score <= prev_score + 0.01
            and issue_count >= prev_issues
            and risk == prev_risk
        ):
            logger.info(
                "RALPH loop early-stop: stagnated (prev_score=%.2f, score=%.2f, prev_issues=%d, issues=%d, risk=%s)",
                prev_score, score, prev_issues, issue_count, risk,
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


# ============================================================
# 共用工作流程
# ============================================================

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
    """共用的公文生成工作流程（同步，需在執行緒池中呼叫）。

    Args:
        user_input: 使用者的自然語言需求描述
        llm: LLM provider 實例
        kb: 知識庫管理器實例
        session_id: 用於產生輸出檔名的唯一識別碼
        skip_review: 是否跳過審查
        max_rounds: 最大修改輪數（經典模式）
        output_docx: 是否輸出 docx 檔案
        output_filename_hint: 輸出檔名提示（未清理）
        convergence: 啟用分層收斂迭代模式
        skip_info: 分層收斂模式下是否跳過 info Phase
        ralph_loop: 啟用 Ralph Loop 極限品質模式
        ralph_max_cycles: Ralph Loop 最大循環次數
        ralph_target_score: Ralph Loop 目標分數

    Returns:
        (requirement, final_draft, qa_report, output_filename, rounds_used)
    """
    if ralph_loop:
        if skip_review:
            logger.info("RALPH loop 啟用時忽略 skip_review=True，改為強制審查")
        skip_review = False

    # 步驟 1: 需求分析
    req_agent = RequirementAgent(llm)
    requirement = req_agent.analyze(user_input)

    # 步驟 1.5: 取得機構記憶偏好（若有啟用）
    writing_hints = ""
    org_mem = get_org_memory()
    if org_mem and requirement.sender:
        writing_hints = org_mem.get_writing_hints(requirement.sender)

    # 步驟 2: 撰寫草稿（注入機構偏好）
    writer = WriterAgent(llm, kb)
    if writing_hints:
        # 將偏好提示附加到需求的 reason 欄位，讓 WriterAgent 在 prompt 中看到
        original_reason = requirement.reason or ""
        requirement.reason = (
            f"{original_reason}\n\n"
            f"【機構寫作偏好】\n{writing_hints}"
        ).strip()
    raw_draft = writer.write_draft(requirement)

    # 步驟 3: 套用模板
    template_engine = TemplateEngine()
    sections = template_engine.parse_draft(raw_draft)
    formatted_draft = template_engine.apply_template(requirement, sections)

    final_draft = formatted_draft
    qa_report = None
    rounds_used = 0

    # 步驟 4: 審查（迭代邏輯已內建於 review_and_refine）
    if not skip_review:
        with EditorInChief(llm, kb) as editor:
            if ralph_loop:
                final_draft, qa_report, rounds_used = _run_ralph_loop(
                    editor,
                    final_draft,
                    requirement.doc_type,
                    max_rounds=max_rounds,
                    max_cycles=ralph_max_cycles,
                    target_score=ralph_target_score,
                )
            else:
                final_draft, qa_report = editor.review_and_refine(
                    final_draft, requirement.doc_type, max_rounds=max_rounds,
                    convergence=convergence, skip_info=skip_info,
                    show_rounds=False,
                )
                rounds_used = qa_report.rounds_used

    # 步驟 4.5: 統一收斂（修正常見文稿瑕疵與引用定義一致性）
    final_draft = writer.normalize_existing_draft(final_draft)
    # 再套一次模板，收斂段落結構與標題格式，避免 review/refine 引入雜訊行
    final_sections = template_engine.parse_draft(final_draft)
    final_draft = template_engine.apply_template(requirement, final_sections)
    final_draft = writer.normalize_existing_draft(final_draft)

    # 步驟 4.8: RALPH 模式下以最終草稿再評一次，避免 QA 分數與輸出內容不同步
    force_post_verify = os.environ.get("API_FORCE_POST_REVIEW_VERIFY", "0") == "1"
    agent_results = getattr(qa_report, "agent_results", None) if qa_report else None
    has_agent_results = isinstance(agent_results, list) and len(agent_results) > 0
    if (ralph_loop or force_post_verify) and (not skip_review) and qa_report is not None and has_agent_results:
        with EditorInChief(llm, kb) as verifier:
            results, timed_out = verifier._execute_review(final_draft, requirement.doc_type)
            verified_report = verifier._generate_qa_report(results, timed_out)

        # 保留原先迭代輪數與歷程，僅更新最終品質評分到最新草稿版本
        verified_report.rounds_used = rounds_used
        previous_history = getattr(qa_report, "iteration_history", None)
        if previous_history:
            verified_report.iteration_history = previous_history

        previous_audit_log = str(getattr(qa_report, "audit_log", "") or "")
        trace_match = re.search(r"\n## Ralph Loop Trace[\s\S]*$", previous_audit_log)
        if trace_match and "## Ralph Loop Trace" not in (verified_report.audit_log or ""):
            verified_report.audit_log = (
                f"{verified_report.audit_log.rstrip()}\n" + trace_match.group(0)
            )

        original_score = float(getattr(qa_report, "overall_score", 0.0) or 0.0)
        verified_score = float(getattr(verified_report, "overall_score", 0.0) or 0.0)
        # 僅在最終複評分數不低於原始分數時採用，避免 LLM 評審波動造成回退。
        if verified_score >= original_score:
            qa_report = verified_report

    # 步驟 5: 匯出（使用固定輸出目錄，避免依賴 cwd）
    output_filename = None
    if output_docx:
        exporter = DocxExporter()
        filename = _sanitize_output_filename(output_filename_hint, session_id)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_DIR, filename)
        exporter.export(
            final_draft,
            output_path,
            qa_report=qa_report.audit_log if qa_report else None,
        )
        # 僅回傳檔名，不回傳完整的伺服器檔案路徑（避免洩漏目錄結構）
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
) -> tuple:
    """透過 LangGraph 執行公文生成流程（同步，需在執行緒池中呼叫）。

    回傳與 _execute_document_workflow 相同的 tuple 結構，以便呼叫端無縫切換。
    機構記憶由 graph 內建的 fetch_org_memory node 處理（從 requirement.sender 讀取），
    不需外部傳入 agency 參數。

    Args:
        user_input: 使用者的自然語言需求描述
        session_id: 用於產生輸出檔名的唯一識別碼
        skip_review: 是否跳過審查
        max_rounds: 最大精煉輪數
        output_docx: 是否輸出 docx 檔案
        output_filename_hint: 輸出檔名提示（未清理）
        convergence: 啟用分層收斂迭代模式
        skip_info: 分層收斂模式下是否跳過 info Phase

    Returns:
        (requirement, final_draft, qa_report, output_filename, rounds_used)
        與 _execute_document_workflow 回傳格式完全一致。
    """
    graph = _get_graph()

    # 組裝初始狀態
    initial_state = {
        "user_input": user_input,
        "review_requested": not skip_review,
        "max_refinement_rounds": max_rounds,
        "refinement_round": 0,
        "review_results": [],
        "phase": "init",
    }

    # 執行 graph
    final_state = graph.invoke(initial_state)

    # ── 從 final_state 萃取結果 ──────────────────────────────

    # 檢查 graph 是否有錯誤
    graph_error = final_state.get("error")
    if graph_error:
        logger.warning("LangGraph 流程出現錯誤: %s", graph_error)

    # requirement: graph 中以 dict 儲存，需重建為 Pydantic model
    requirement_dict = final_state.get("requirement") or {}
    if not requirement_dict:
        # graph 中 parse_requirement 失敗，無法建構需求物件
        raise ValueError(f"LangGraph 需求分析失敗: {graph_error or '未知原因'}")
    requirement = PublicDocRequirement(**requirement_dict)

    # final_draft: 優先取精煉版，其次格式化版，最後原始草稿
    final_draft = (
        final_state.get("refined_draft")
        or final_state.get("formatted_draft")
        or final_state.get("draft")
        or ""
    )
    if not final_draft.strip():
        logger.warning(
            "LangGraph 草稿為空 (phase=%s, error=%s)",
            final_state.get("phase"), graph_error,
        )

    # qa_report: 從 aggregated_report 建構，供 API 回傳
    # 原始 workflow 回傳 QAReport Pydantic model，但 API 端只呼叫 .model_dump()
    # 這裡直接回傳一個具有相同介面的簡易物件
    aggregated = final_state.get("aggregated_report")
    report_md = final_state.get("report", "")
    rounds_used = final_state.get("refinement_round", 0)

    qa_report = None
    if aggregated and not skip_review:
        qa_report = _GraphQAReport(
            overall_score=aggregated.get("overall_score", 0.0),
            risk_summary=aggregated.get("risk_summary", "Unknown"),
            error_count=aggregated.get("error_count", 0),
            warning_count=aggregated.get("warning_count", 0),
            agent_results=aggregated.get("agent_results", []),
            rounds_used=rounds_used,
            report_markdown=report_md,
            audit_log=report_md,
        )

    # 清理 graph 自動產生的臨時匯出檔（API 層自行控制匯出命名）
    _graph_output = final_state.get("output_path")
    if _graph_output and os.path.isfile(_graph_output):
        try:
            os.remove(_graph_output)
            logger.debug("已清理 graph 臨時匯出檔: %s", _graph_output)
        except OSError:
            pass

    # 步驟 5: 匯出 DOCX（沿用原始 workflow 的匯出邏輯，不依賴 graph 的 export_docx node）
    output_filename = None
    if output_docx:
        exporter = DocxExporter()
        filename = _sanitize_output_filename(output_filename_hint, session_id)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_DIR, filename)
        exporter.export(
            final_draft,
            output_path,
            qa_report=qa_report.audit_log if qa_report else None,
        )
        output_filename = filename

    return requirement, final_draft, qa_report, output_filename, rounds_used


class _GraphQAReport:
    """輕量 QA 報告物件，模擬原始 QAReport 的 API 介面。

    原始 EditorInChief 回傳的 QAReport 是 Pydantic model，
    API 端呼叫 .model_dump() 序列化。此類別提供相同的
    model_dump() 方法和 rounds_used / audit_log 屬性，
    確保與現有 API 回傳格式完全相容。
    """

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


# ============================================================
# Meeting 端點
# ============================================================

@router.post(
    "/api/v1/meeting",
    response_model=MeetingResponse,
    tags=["完整流程"],
)
async def run_meeting(request: MeetingRequest) -> MeetingResponse:
    """完整開會流程

    一鍵執行：需求分析 -> 撰寫 -> 審查 -> 修改 -> 輸出 DOCX。
    支援 use_graph 參數切換 LangGraph 新路徑 / 傳統路徑。
    """
    session_id = str(uuid.uuid4())[:SESSION_ID_LENGTH]

    try:
        # convergence 模式需要分層收斂迭代（error→warning→info phase），
        # 目前僅傳統路徑的 EditorInChief 支援，LangGraph 的 should_refine
        # 只做簡單 round-based 判定。RALPH loop 也依賴傳統路徑。
        # 自動 fallback 避免靜默忽略。
        effective_use_graph = request.use_graph
        if request.use_graph and (request.convergence or request.ralph_loop):
            logger.info(
                "use_graph=True 與 convergence/ralph_loop 同時啟用，"
                "自動切換至傳統路徑（LangGraph 尚未支援分層收斂/極限迭代）"
            )
            effective_use_graph = False

        if effective_use_graph:
            # ── 新路徑：LangGraph 流程圖 ──────────────────
            try:
                requirement, final_draft, qa_report, output_filename, rounds_used = (
                    await run_in_executor(
                        lambda: _execute_via_graph(
                            user_input=request.user_input,
                            session_id=session_id,
                            skip_review=request.skip_review,
                            max_rounds=request.max_rounds,
                            output_docx=request.output_docx,
                            output_filename_hint=request.output_filename,
                            convergence=request.convergence,
                            skip_info=request.skip_info,
                            ralph_loop=request.ralph_loop,
                            ralph_max_cycles=request.ralph_max_cycles,
                            ralph_target_score=request.ralph_target_score,
                        ),
                        timeout=MEETING_TIMEOUT,
                    )
                )
            except Exception as graph_err:
                # Graph 執行失敗，自動 fallback 到傳統路徑
                logger.warning(
                    "LangGraph 執行失敗，fallback 到傳統路徑: %s", graph_err
                )
                llm = get_llm()
                kb = get_kb()
                requirement, final_draft, qa_report, output_filename, rounds_used = (
                    await run_in_executor(
                        lambda: _execute_document_workflow(
                            user_input=request.user_input,
                            llm=llm,
                            kb=kb,
                            session_id=session_id,
                            skip_review=request.skip_review,
                            max_rounds=request.max_rounds,
                            output_docx=request.output_docx,
                            output_filename_hint=request.output_filename,
                            convergence=request.convergence,
                            skip_info=request.skip_info,
                            ralph_loop=request.ralph_loop,
                            ralph_max_cycles=request.ralph_max_cycles,
                            ralph_target_score=request.ralph_target_score,
                        ),
                        timeout=MEETING_TIMEOUT,
                    )
                )
        else:
            # ── 傳統路徑 ──────────────────────────────────
            llm = get_llm()
            kb = get_kb()
            requirement, final_draft, qa_report, output_filename, rounds_used = (
                await run_in_executor(
                    lambda: _execute_document_workflow(
                        user_input=request.user_input,
                        llm=llm,
                        kb=kb,
                        session_id=session_id,
                        skip_review=request.skip_review,
                        max_rounds=request.max_rounds,
                        output_docx=request.output_docx,
                        output_filename_hint=request.output_filename,
                        convergence=request.convergence,
                        skip_info=request.skip_info,
                        ralph_loop=request.ralph_loop,
                        ralph_max_cycles=request.ralph_max_cycles,
                        ralph_target_score=request.ralph_target_score,
                    ),
                    timeout=MEETING_TIMEOUT,
                )
            )

        requirement_dict = requirement.model_dump()
        qa_report_dict = qa_report.model_dump() if qa_report else None
        _cache_detailed_review(
            session_id=session_id,
            requirement=requirement_dict,
            final_draft=final_draft,
            qa_report=qa_report_dict,
            rounds_used=rounds_used,
        )

        return MeetingResponse(
            success=True,
            session_id=session_id,
            requirement=requirement_dict,
            final_draft=final_draft,
            qa_report=qa_report_dict,
            output_path=output_filename,
            rounds_used=rounds_used,
        )

    except Exception as e:
        logger.exception("開會流程失敗")
        return MeetingResponse(
            success=False,
            session_id=session_id,
            error=_sanitize_error(e),
            error_code=_get_error_code(e),
        )


# ============================================================
# 詳細審查報告查詢
# ============================================================

@router.get(
    "/api/v1/detailed-review",
    tags=["完整流程"],
)
async def get_detailed_review(session_id: str = ""):
    """依 session_id 查詢詳細審查報告。"""
    if not session_id:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "缺少 session_id 參數"},
        )

    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", session_id):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "session_id 格式無效"},
        )

    payload = _get_cached_detailed_review(session_id)
    if payload is None:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "找不到對應的審查報告"},
        )

    return payload


# ============================================================
# 檔案下載
# ============================================================

@router.get(
    "/api/v1/download/{filename}",
    tags=["文件下載"],
)
async def download_file(filename: str):
    """下載生成的 DOCX 檔案"""
    # 第一層防護：正則表達式檔名驗證（防止路徑遍歷字元）
    if not re.match(r"^[a-zA-Z0-9_\-\.]+\.docx$", filename):
        return JSONResponse(status_code=400, content={"detail": "無效的檔案名稱"})

    # 第二層防護：Path.resolve() 確保解析後的路徑在允許的輸出目錄內
    output_dir = OUTPUT_DIR.resolve()
    file_path = (output_dir / filename).resolve()
    if not file_path.is_relative_to(output_dir):
        logger.warning("路徑遍歷攻擊嘗試: filename=%s, resolved=%s", filename, file_path)
        return JSONResponse(status_code=400, content={"detail": "無效的檔案名稱"})

    # 第三層防護：拒絕 symlink（防止繞過路徑驗證讀取任意檔案）
    if (output_dir / filename).is_symlink():
        logger.warning("Symlink 攻擊嘗試: filename=%s", filename)
        return JSONResponse(status_code=400, content={"detail": "無效的檔案名稱"})

    if not file_path.is_file():
        return JSONResponse(status_code=404, content={"detail": "檔案不存在"})

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# ============================================================
# 批次處理
# ============================================================

@router.post(
    "/api/v1/batch",
    response_model=BatchResponse,
    tags=["批次處理"],
)
async def run_batch(request: BatchRequest) -> BatchResponse:
    """批次處理多筆公文需求

    依序執行每筆完整開會流程，個別失敗不影響其他項目。
    回傳包含進度追蹤、每項處理時間及整體耗時。
    """
    batch_start = time.monotonic()

    # 並行執行：模組級 Semaphore 控制同時最多 3 筆，避免 ThreadPoolExecutor 過載

    async def _process_item(item) -> BatchItemResult:
        session_id = str(uuid.uuid4())[:SESSION_ID_LENGTH]
        item_start = time.monotonic()
        async with _BATCH_SEMAPHORE:
            try:
                llm = get_llm()
                kb = get_kb()

                requirement, final_draft, qa_report, output_filename, rounds_used = (
                    await run_in_executor(
                        lambda req=item, _llm=llm, _kb=kb, _sid=session_id: _execute_document_workflow(
                            user_input=req.user_input,
                            llm=_llm,
                            kb=_kb,
                            session_id=_sid,
                            skip_review=req.skip_review,
                            max_rounds=req.max_rounds,
                            output_docx=req.output_docx,
                            output_filename_hint=req.output_filename,
                            convergence=req.convergence,
                            skip_info=req.skip_info,
                            ralph_loop=req.ralph_loop,
                            ralph_max_cycles=req.ralph_max_cycles,
                            ralph_target_score=req.ralph_target_score,
                        ),
                        timeout=MEETING_TIMEOUT,
                    )
                )

                item_duration = round((time.monotonic() - item_start) * 1000, 2)
                requirement_dict = requirement.model_dump()
                qa_report_dict = qa_report.model_dump() if qa_report else None
                _cache_detailed_review(
                    session_id=session_id,
                    requirement=requirement_dict,
                    final_draft=final_draft,
                    qa_report=qa_report_dict,
                    rounds_used=rounds_used,
                )
                return BatchItemResult(
                    status="success",
                    duration_ms=item_duration,
                    error_message=None,
                    success=True,
                    session_id=session_id,
                    requirement=requirement_dict,
                    final_draft=final_draft,
                    qa_report=qa_report_dict,
                    output_path=output_filename,
                    rounds_used=rounds_used,
                )

            except Exception as e:
                logger.exception("批次處理項目失敗")
                item_duration = round((time.monotonic() - item_start) * 1000, 2)
                sanitized = _sanitize_error(e)
                return BatchItemResult(
                    status="error",
                    duration_ms=item_duration,
                    error_message=sanitized,
                    success=False,
                    session_id=session_id,
                    error=sanitized,
                    error_code=_get_error_code(e),
                )

    # 所有項目同時啟動，由 Semaphore 控制並行度，總體超時防止 HTTP 連線無限掛起
    try:
        results: list[BatchItemResult] = await asyncio.wait_for(
            asyncio.gather(*[_process_item(item) for item in request.items]),
            timeout=BATCH_TOTAL_TIMEOUT,
        )
    except asyncio.TimeoutError:
        total_duration = round((time.monotonic() - batch_start) * 1000, 2)
        logger.error(
            "批次處理總體超時 (%ds)，已處理時間: %.0fms",
            BATCH_TOTAL_TIMEOUT, total_duration,
        )
        raise HTTPException(
            status_code=504,
            detail=f"批次處理超過總體時限 ({BATCH_TOTAL_TIMEOUT}s)，請減少項目數量或調整 API_BATCH_TOTAL_TIMEOUT",
        )

    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count
    total_duration = round((time.monotonic() - batch_start) * 1000, 2)
    total_items = len(request.items)

    return BatchResponse(
        results=results,
        progress={
            "completed": total_items,
            "total": total_items,
        },
        total_duration_ms=total_duration,
        summary={
            "total": total_items,
            "success": success_count,
            "failed": fail_count,
        },
    )
