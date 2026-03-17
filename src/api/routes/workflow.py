"""
完整工作流程路由 — Meeting、檔案下載、批次處理
=============================================
"""

import logging
import os
import re
import time
import uuid
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from src.core.constants import SESSION_ID_LENGTH
from src.core.models import PublicDocRequirement
from src.agents.editor import EditorInChief
from src.agents.requirement import RequirementAgent
from src.agents.writer import WriterAgent
from src.agents.template import TemplateEngine
from src.document.exporter import DocxExporter

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
    agency: str | None = None,
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
        agency: 機構名稱（用於取得機構記憶偏好）
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
    # 優先使用呼叫端指定的機構名稱，否則使用需求中的 sender
    resolved_agency = agency or requirement.sender
    if org_mem and resolved_agency:
        writing_hints = org_mem.get_writing_hints(resolved_agency)

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
        editor = EditorInChief(llm, kb)
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
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "output")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, filename)
        exporter.export(
            final_draft,
            output_path,
            qa_report=qa_report.audit_log if qa_report else None,
        )
        # 僅回傳檔名，不回傳完整的伺服器檔案路徑（避免洩漏目錄結構）
        output_filename = filename

    return requirement, final_draft, qa_report, output_filename, rounds_used


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
    """
    session_id = str(uuid.uuid4())[:SESSION_ID_LENGTH]

    try:
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
    output_dir = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "output").resolve()
    file_path = (output_dir / filename).resolve()
    if not file_path.is_relative_to(output_dir):
        logger.warning("路徑遍歷攻擊嘗試: filename=%s, resolved=%s", filename, file_path)
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
    results: list[BatchItemResult] = []
    success_count = 0
    fail_count = 0
    batch_start = time.monotonic()

    for item in request.items:
        session_id = str(uuid.uuid4())[:SESSION_ID_LENGTH]
        item_start = time.monotonic()
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
            results.append(
                BatchItemResult(
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
            )
            success_count += 1

        except Exception as e:
            logger.exception("批次處理項目失敗")
            item_duration = round((time.monotonic() - item_start) * 1000, 2)
            sanitized = _sanitize_error(e)
            results.append(
                BatchItemResult(
                    status="error",
                    duration_ms=item_duration,
                    error_message=sanitized,
                    success=False,
                    session_id=session_id,
                    error=sanitized,
                    error_code=_get_error_code(e),
                )
            )
            fail_count += 1

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
