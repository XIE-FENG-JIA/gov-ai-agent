"""Individual review agent route handlers (format / style / fact / consistency / compliance)."""
import logging

from fastapi import APIRouter, Depends

from src.agents.style_checker import StyleChecker
from src.agents.fact_checker import FactChecker
from src.agents.consistency_checker import ConsistencyChecker
from src.agents.compliance_checker import ComplianceChecker
from src.agents.auditor import FormatAuditor
from src.agents.review_parser import format_audit_to_review_result

from src.api.auth import require_api_key
from src.api.dependencies import get_llm, get_kb
from src.api.helpers import (
    _sanitize_error,
    _get_error_code,
    review_result_to_dict,
    run_in_executor,
)
from src.api.models import ReviewRequest, ReviewResponse

logger = logging.getLogger(__name__)

review_router = APIRouter()
_REVIEW_WRITE_AUTH = [Depends(require_api_key)]
_REVIEW_EXCEPTIONS = (
    ConnectionError,
    FileNotFoundError,
    KeyError,
    OSError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
)


def _log_review_warning(endpoint: str, exc: Exception) -> None:
    logger.warning("%s 失敗: %s", endpoint, exc)


@review_router.post(
    "/api/v1/agent/review/format",
    response_model=ReviewResponse,
    tags=["審查"],
    dependencies=_REVIEW_WRITE_AUTH,
)
async def review_format(request: ReviewRequest) -> ReviewResponse:
    """格式審查 Agent

    檢查公文是否符合標準格式規範（主旨、說明、辦法等段落結構）。
    """
    try:
        auditor = FormatAuditor(get_llm(), get_kb())
        fmt_raw = await run_in_executor(
            lambda: auditor.audit(request.draft, request.doc_type)
        )
        result = format_audit_to_review_result(fmt_raw)
        return ReviewResponse(
            success=True,
            agent_name="format",
            result=review_result_to_dict(result),
        )
    except _REVIEW_EXCEPTIONS as e:
        _log_review_warning("格式審查", e)
        return ReviewResponse(
            success=False, agent_name="format", error=_sanitize_error(e), error_code=_get_error_code(e)
        )


@review_router.post(
    "/api/v1/agent/review/style",
    response_model=ReviewResponse,
    tags=["審查"],
    dependencies=_REVIEW_WRITE_AUTH,
)
async def review_style(request: ReviewRequest) -> ReviewResponse:
    """文風審查 Agent

    檢查公文用語是否正式、語氣是否得體。
    """
    try:
        checker = StyleChecker(get_llm())
        result = await run_in_executor(lambda: checker.check(request.draft))
        return ReviewResponse(
            success=True,
            agent_name="style",
            result=review_result_to_dict(result),
        )
    except _REVIEW_EXCEPTIONS as e:
        _log_review_warning("文風審查", e)
        return ReviewResponse(
            success=False, agent_name="style", error=_sanitize_error(e), error_code=_get_error_code(e)
        )


@review_router.post(
    "/api/v1/agent/review/fact",
    response_model=ReviewResponse,
    tags=["審查"],
    dependencies=_REVIEW_WRITE_AUTH,
)
async def review_fact(request: ReviewRequest) -> ReviewResponse:
    """事實審查 Agent

    檢查公文中的事實陳述、日期、法規引用是否正確。
    """
    try:
        checker = FactChecker(get_llm())
        result = await run_in_executor(lambda: checker.check(request.draft, doc_type=request.doc_type))
        return ReviewResponse(
            success=True,
            agent_name="fact",
            result=review_result_to_dict(result),
        )
    except _REVIEW_EXCEPTIONS as e:
        _log_review_warning("事實審查", e)
        return ReviewResponse(
            success=False, agent_name="fact", error=_sanitize_error(e), error_code=_get_error_code(e)
        )


@review_router.post(
    "/api/v1/agent/review/consistency",
    response_model=ReviewResponse,
    tags=["審查"],
    dependencies=_REVIEW_WRITE_AUTH,
)
async def review_consistency(request: ReviewRequest) -> ReviewResponse:
    """一致性審查 Agent

    檢查公文內部邏輯是否一致、前後文是否矛盾。
    """
    try:
        checker = ConsistencyChecker(get_llm())
        result = await run_in_executor(lambda: checker.check(request.draft))
        return ReviewResponse(
            success=True,
            agent_name="consistency",
            result=review_result_to_dict(result),
        )
    except _REVIEW_EXCEPTIONS as e:
        _log_review_warning("一致性審查", e)
        return ReviewResponse(
            success=False, agent_name="consistency", error=_sanitize_error(e), error_code=_get_error_code(e)
        )


@review_router.post(
    "/api/v1/agent/review/compliance",
    response_model=ReviewResponse,
    tags=["審查"],
    dependencies=_REVIEW_WRITE_AUTH,
)
async def review_compliance(request: ReviewRequest) -> ReviewResponse:
    """政策合規審查 Agent

    檢查公文內容是否符合相關法規與政策要求。
    """
    try:
        checker = ComplianceChecker(get_llm(), get_kb())
        result = await run_in_executor(lambda: checker.check(request.draft))
        return ReviewResponse(
            success=True,
            agent_name="compliance",
            result=review_result_to_dict(result),
        )
    except _REVIEW_EXCEPTIONS as e:
        _log_review_warning("合規審查", e)
        return ReviewResponse(
            success=False, agent_name="compliance", error=_sanitize_error(e), error_code=_get_error_code(e)
        )
