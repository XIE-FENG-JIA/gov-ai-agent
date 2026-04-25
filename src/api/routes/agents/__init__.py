"""Agent 路由 — 需求分析、撰寫、並行審查、修改。個別審查路由見 _review_routes.py。"""
import logging
from typing import Any

from fastapi import APIRouter, Depends

from src.core.models import PublicDocRequirement
from src.agents.requirement import RequirementAgent
from src.agents.writer import WriterAgent
from src.agents.template import TemplateEngine
from src.agents.style_checker import StyleChecker
from src.agents.fact_checker import FactChecker
from src.agents.consistency_checker import ConsistencyChecker
from src.agents.compliance_checker import ComplianceChecker
from src.agents.auditor import FormatAuditor
from src.agents.review_parser import format_audit_to_review_result
from src.core.llm import LLMError

from src.api.auth import require_api_key
from src.api.dependencies import get_llm, get_kb
import src.api.dependencies as _deps
from src.api.routes._agents_parallel import run_parallel_review, run_format_audit as _run_format_audit_impl
from src.api.helpers import (
    _sanitize_error,
    _get_error_code,
    review_result_to_dict,  # noqa: F401
    run_in_executor,
)
from src.api.models import (
    RequirementRequest,
    RequirementResponse,
    WriterRequest,
    WriterResponse,
    ParallelReviewRequest,
    ParallelReviewResponse,
    RefineRequest,
    RefineResponse,
)
from src.api.routes.agents._review_routes import review_router
from src.api.routes.agents._refine_helpers import _build_feedback_str, _build_refine_prompt, _is_empty_or_error

logger = logging.getLogger(__name__)

router = APIRouter()
WRITE_AUTH = [Depends(require_api_key)]
_AGENT_ROUTE_EXCEPTIONS = (
    ConnectionError,
    FileNotFoundError,
    KeyError,
    LLMError,
    OSError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
)

# 個別審查路由已在 _review_routes.py 中定義，此處 include 進主 router
router.include_router(review_router)


def _log_agent_warning(endpoint: str, exc: Exception) -> None:
    """記錄已知可降級的 agent route 失敗。"""
    logger.warning("%s 失敗: %s", endpoint, exc)


def _run_format_audit(draft: str, doc_type: str, llm: Any, kb: Any) -> Any:
    """保留既有 patch 面，實際邏輯委派給 helper module。"""
    return _run_format_audit_impl(draft, doc_type, llm, kb, FormatAuditor, format_audit_to_review_result)


# ------------------------------------------------------------
# 1. Requirement Agent
# ------------------------------------------------------------

@router.post(
    "/api/v1/agent/requirement",
    response_model=RequirementResponse,
    tags=["需求分析"],
    dependencies=WRITE_AUTH,
)
async def analyze_requirement(request: RequirementRequest) -> RequirementResponse:
    """需求分析 Agent

    將用戶的自然語言描述轉換為結構化的公文需求（doc_type, sender, receiver 等）。
    """
    try:
        agent = RequirementAgent(get_llm())
        requirement = await run_in_executor(
            lambda: agent.analyze(request.user_input)
        )
        return RequirementResponse(
            success=True,
            requirement=requirement.model_dump(),
        )
    except _AGENT_ROUTE_EXCEPTIONS as e:
        _log_agent_warning("需求分析", e)
        return RequirementResponse(success=False, error=_sanitize_error(e), error_code=_get_error_code(e))


# ------------------------------------------------------------
# 2. Writer Agent
# ------------------------------------------------------------

@router.post(
    "/api/v1/agent/writer",
    response_model=WriterResponse,
    tags=["草稿撰寫"],
    dependencies=WRITE_AUTH,
)
async def write_draft(request: WriterRequest) -> WriterResponse:
    """撰寫 Agent

    根據結構化需求（來自 requirement agent）撰寫公文草稿，
    並套用標準模板格式。
    """
    try:
        requirement = PublicDocRequirement(**request.requirement)
        writer = WriterAgent(get_llm(), get_kb())

        def _write_and_format():
            raw = writer.write_draft(requirement)
            engine = TemplateEngine()
            sections = engine.parse_draft(raw)
            formatted = engine.apply_template(requirement, sections)
            return raw, formatted

        raw_draft, formatted_draft = await run_in_executor(_write_and_format)

        return WriterResponse(
            success=True,
            draft=raw_draft,
            formatted_draft=formatted_draft,
        )
    except _AGENT_ROUTE_EXCEPTIONS as e:
        _log_agent_warning("草稿撰寫", e)
        return WriterResponse(success=False, error=_sanitize_error(e), error_code=_get_error_code(e))


# ------------------------------------------------------------
# 4. Parallel Review
# ------------------------------------------------------------

@router.post(
    "/api/v1/agent/review/parallel",
    response_model=ParallelReviewResponse,
    tags=["審查"],
    dependencies=WRITE_AUTH,
)
async def parallel_review(
    request: ParallelReviewRequest,
) -> ParallelReviewResponse:
    """並行審查

    同時執行多個審查 Agent（格式、文風、事實、一致性、合規），
    彙整加權分數與風險等級。
    """
    try:
        return await run_parallel_review(
            request,
            llm=get_llm(),
            kb=get_kb(),
            executor=_deps.executor,
            format_runner=_run_format_audit,
            style_checker_cls=StyleChecker,
            fact_checker_cls=FactChecker,
            consistency_checker_cls=ConsistencyChecker,
            compliance_checker_cls=ComplianceChecker,
        )
    except _AGENT_ROUTE_EXCEPTIONS as e:
        _log_agent_warning("並行審查", e)
        return ParallelReviewResponse(
            success=False,
            results={},
            aggregated_score=0.0,
            risk_summary="Critical",
            error=_sanitize_error(e),
            error_code=_get_error_code(e),
        )


# ------------------------------------------------------------
# 5. Editor (Refine)
# ------------------------------------------------------------

@router.post(
    "/api/v1/agent/refine",
    response_model=RefineResponse,
    tags=["修改"],
    dependencies=WRITE_AUTH,
)
async def refine_draft(request: RefineRequest) -> RefineResponse:
    """Editor Agent

    根據審查 Agent 回傳的問題列表，自動修正公文草稿。
    # PRESERVE all 【待補依據】 markers - do NOT replace with fabricated citations.
    """
    try:
        llm = get_llm()

        feedback_str = _build_feedback_str(request.feedback)
        if not feedback_str:
            return RefineResponse(success=True, refined_draft=request.draft)

        prompt = _build_refine_prompt(request.draft, feedback_str)

        # 在執行緒池中執行阻塞的 LLM 呼叫
        refined = await run_in_executor(lambda: llm.generate(prompt))

        # 若 LLM 回傳空值，保留原始草稿
        if _is_empty_or_error(refined):
            return RefineResponse(success=True, refined_draft=request.draft)

        return RefineResponse(success=True, refined_draft=refined)

    except _AGENT_ROUTE_EXCEPTIONS as e:
        _log_agent_warning("草稿修改", e)
        return RefineResponse(success=False, error=_sanitize_error(e), error_code=_get_error_code(e))
