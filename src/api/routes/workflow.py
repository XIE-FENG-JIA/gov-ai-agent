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

from fastapi import APIRouter
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

    Returns:
        (requirement, final_draft, qa_report, output_filename, rounds_used)
    """
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
            final_draft, qa_report = editor.review_and_refine(
                final_draft, requirement.doc_type, max_rounds=max_rounds,
                convergence=convergence, skip_info=skip_info,
                show_rounds=False,
            )
            rounds_used = qa_report.rounds_used

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
        # 只做簡單 round-based 判定。自動 fallback 避免靜默忽略。
        effective_use_graph = request.use_graph
        if request.use_graph and request.convergence:
            logger.info(
                "convergence=True 與 use_graph=True 同時啟用，"
                "自動切換至傳統路徑（LangGraph 尚未支援分層收斂迭代）"
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
                    ),
                    timeout=MEETING_TIMEOUT,
                )
            )

        return MeetingResponse(
            success=True,
            session_id=session_id,
            requirement=requirement.model_dump(),
            final_draft=final_draft,
            qa_report=qa_report.model_dump() if qa_report else None,
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
                        ),
                        timeout=MEETING_TIMEOUT,
                    )
                )

                item_duration = round((time.monotonic() - item_start) * 1000, 2)
                return BatchItemResult(
                    status="success",
                    duration_ms=item_duration,
                    error_message=None,
                    success=True,
                    session_id=session_id,
                    requirement=requirement.model_dump(),
                    final_draft=final_draft,
                    qa_report=qa_report.model_dump() if qa_report else None,
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

    # 所有項目同時啟動，由 Semaphore 控制並行度
    results: list[BatchItemResult] = await asyncio.gather(
        *[_process_item(item) for item in request.items]
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
