"""
workflow package 的 FastAPI 端點。
"""

import asyncio
import re
import time
import uuid
from importlib import import_module

from fastapi import Depends
from fastapi.responses import JSONResponse

from src.api.auth import require_api_key
from src.api.models import BatchItemResult, BatchRequest, BatchResponse, MeetingRequest, MeetingResponse

from ._state import logger, router

WRITE_AUTH = [Depends(require_api_key)]
_WORKFLOW_ENDPOINT_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TimeoutError, TypeError, ValueError, Exception)


def _workflow_package():
    return import_module(__package__)


@router.post(
    "/api/v1/meeting",
    response_model=MeetingResponse,
    tags=["完整流程"],
    dependencies=WRITE_AUTH,
)
async def run_meeting(request: MeetingRequest) -> MeetingResponse:
    """完整開會流程。"""
    workflow = _workflow_package()
    session_id = str(uuid.uuid4())[: workflow.SESSION_ID_LENGTH]

    try:
        effective_use_graph = request.use_graph
        if request.use_graph and (request.convergence or request.ralph_loop):
            logger.info(
                "use_graph=True 與 convergence/ralph_loop 同時啟用，自動切換至傳統路徑（LangGraph 尚未支援分層收斂/極限迭代）"
            )
            effective_use_graph = False

        if effective_use_graph:
            try:
                requirement, final_draft, qa_report, output_filename, rounds_used = await workflow.run_in_executor(
                    lambda: workflow._execute_via_graph(
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
                    timeout=workflow.MEETING_TIMEOUT,
                )
            except _WORKFLOW_ENDPOINT_EXCEPTIONS as graph_err:
                logger.warning("LangGraph 執行失敗，fallback 到傳統路徑: %s", graph_err)
                llm = workflow.get_llm()
                kb = workflow.get_kb()
                requirement, final_draft, qa_report, output_filename, rounds_used = await workflow.run_in_executor(
                    lambda: workflow._execute_document_workflow(
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
                    timeout=workflow.MEETING_TIMEOUT,
                )
        else:
            llm = workflow.get_llm()
            kb = workflow.get_kb()
            requirement, final_draft, qa_report, output_filename, rounds_used = await workflow.run_in_executor(
                lambda: workflow._execute_document_workflow(
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
                timeout=workflow.MEETING_TIMEOUT,
            )

        requirement_dict = requirement.model_dump()
        qa_report_dict = qa_report.model_dump() if qa_report else None
        workflow._cache_detailed_review(
            session_id=session_id,
            requirement=requirement_dict,
            final_draft=final_draft,
            qa_report=qa_report_dict,
            rounds_used=rounds_used,
        )

        # 2026-04-27 fire-and-forget Discord push（取代 watcher daemon 解 docx）
        try:
            from src.api.routes.workflow._discord_push import schedule_push
            schedule_push(
                session_id=session_id,
                user_input=request.user_input,
                output_path=output_filename,
                qa_report=qa_report_dict,
            )
        except Exception as _push_err:  # noqa: BLE001 -- fire-and-forget; Discord push must never fail meeting response
            logger.debug("discord push skipped: %s", _push_err)

        return workflow.MeetingResponse(
            success=True,
            session_id=session_id,
            requirement=requirement_dict,
            final_draft=final_draft,
            qa_report=qa_report_dict,
            output_path=output_filename,
            rounds_used=rounds_used,
        )
    except _WORKFLOW_ENDPOINT_EXCEPTIONS as exc:
        logger.exception("開會流程失敗")
        return workflow.MeetingResponse(
            success=False,
            session_id=session_id,
            error=workflow._sanitize_error(exc),
            error_code=workflow._get_error_code(exc),
        )


@router.get(
    "/api/v1/detailed-review",
    tags=["完整流程"],
)
async def get_detailed_review(session_id: str = ""):
    """依 session_id 查詢詳細審查報告。"""
    workflow = _workflow_package()
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

    payload = workflow._get_cached_detailed_review(session_id)
    if payload is None:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "找不到對應的審查報告"},
        )
    return payload


@router.get(
    "/api/v1/download/{filename}",
    tags=["文件下載"],
)
async def download_file(filename: str):
    """下載生成的 DOCX 檔案。"""
    workflow = _workflow_package()
    if not re.match(r"^[a-zA-Z0-9_\-\.]+\.docx$", filename):
        return JSONResponse(status_code=400, content={"detail": "無效的檔案名稱"})

    output_dir = workflow.OUTPUT_DIR.resolve()
    file_path = (output_dir / filename).resolve()
    if not file_path.is_relative_to(output_dir):
        logger.warning("路徑遍歷攻擊嘗試: filename=%s, resolved=%s", filename, file_path)
        return JSONResponse(status_code=400, content={"detail": "無效的檔案名稱"})

    if (output_dir / filename).is_symlink():
        logger.warning("Symlink 攻擊嘗試: filename=%s", filename)
        return JSONResponse(status_code=400, content={"detail": "無效的檔案名稱"})

    if not file_path.is_file():
        return JSONResponse(status_code=404, content={"detail": "檔案不存在"})

    return workflow.FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.post(
    "/api/v1/batch",
    response_model=BatchResponse,
    tags=["批次處理"],
    dependencies=WRITE_AUTH,
)
async def run_batch(request: BatchRequest) -> BatchResponse:
    """批次處理多筆公文需求。"""
    workflow = _workflow_package()
    batch_start = time.monotonic()

    async def _process_item(item):
        session_id = str(uuid.uuid4())[: workflow.SESSION_ID_LENGTH]
        item_start = time.monotonic()
        async with workflow._BATCH_SEMAPHORE:
            try:
                llm = workflow.get_llm()
                kb = workflow.get_kb()
                requirement, final_draft, qa_report, output_filename, rounds_used = await workflow.run_in_executor(
                    lambda req=item, _llm=llm, _kb=kb, _sid=session_id: workflow._execute_document_workflow(
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
                    timeout=workflow.MEETING_TIMEOUT,
                )

                item_duration = round((time.monotonic() - item_start) * 1000, 2)
                requirement_dict = requirement.model_dump()
                qa_report_dict = qa_report.model_dump() if qa_report else None
                workflow._cache_detailed_review(
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
            except _WORKFLOW_ENDPOINT_EXCEPTIONS as exc:
                logger.exception("批次處理項目失敗")
                item_duration = round((time.monotonic() - item_start) * 1000, 2)
                sanitized = workflow._sanitize_error(exc)
                return BatchItemResult(
                    status="error",
                    duration_ms=item_duration,
                    error_message=sanitized,
                    success=False,
                    session_id=session_id,
                    error=sanitized,
                    error_code=workflow._get_error_code(exc),
                )

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*[_process_item(item) for item in request.items]),
            timeout=workflow.BATCH_TOTAL_TIMEOUT,
        )
    except asyncio.TimeoutError:
        total_duration = round((time.monotonic() - batch_start) * 1000, 2)
        logger.error("批次處理總體超時 (%ds)，已處理時間: %.0fms", workflow.BATCH_TOTAL_TIMEOUT, total_duration)
        raise workflow.HTTPException(
            status_code=504,
            detail=f"批次處理超過總體時限 ({workflow.BATCH_TOTAL_TIMEOUT}s)，請減少項目數量或調整 API_BATCH_TOTAL_TIMEOUT",
        )

    success_count = sum(1 for result in results if result.success)
    fail_count = len(results) - success_count
    total_duration = round((time.monotonic() - batch_start) * 1000, 2)
    total_items = len(request.items)

    return workflow.BatchResponse(
        results=results,
        progress={"completed": total_items, "total": total_items},
        total_duration_ms=total_duration,
        summary={"total": total_items, "success": success_count, "failed": fail_count},
    )
