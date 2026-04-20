"""
完整工作流程路由 package。
"""

from fastapi import HTTPException
from fastapi.responses import FileResponse

from src.agents.editor import EditorInChief
from src.agents.requirement import RequirementAgent
from src.agents.template import TemplateEngine
from src.agents.writer import WriterAgent
from src.api.dependencies import get_kb, get_llm, get_org_memory
from src.api.helpers import (
    BATCH_TOTAL_TIMEOUT,
    MEETING_TIMEOUT,
    _get_error_code,
    _sanitize_error,
    _sanitize_output_filename,
    run_in_executor,
)
from src.api.models import (
    BatchItemResult,
    BatchRequest,
    BatchResponse,
    MeetingRequest,
    MeetingResponse,
)
from src.core.constants import OUTPUT_DIR, SESSION_ID_LENGTH
from src.core.models import PublicDocRequirement
from src.document.exporter import DocxExporter
from src.graph import build_graph

from ._endpoints import download_file, get_detailed_review, run_batch, run_meeting
from ._execution import (
    _GraphQAReport,
    _count_report_issues,
    _execute_document_workflow,
    _execute_via_graph,
    _is_ralph_goal_met,
    _run_ralph_loop,
)
from ._state import (
    _BATCH_SEMAPHORE,
    _DETAILED_REVIEW_MAX_ITEMS,
    _DETAILED_REVIEW_STORE,
    _GRAPH,
    _cache_detailed_review,
    _detailed_review_lock,
    _get_cached_detailed_review,
    _get_graph,
    _graph_lock,
    logger,
    router,
)

__all__ = [
    "BATCH_TOTAL_TIMEOUT",
    "BatchItemResult",
    "BatchRequest",
    "BatchResponse",
    "DocxExporter",
    "EditorInChief",
    "FileResponse",
    "HTTPException",
    "MEETING_TIMEOUT",
    "MeetingRequest",
    "MeetingResponse",
    "OUTPUT_DIR",
    "PublicDocRequirement",
    "RequirementAgent",
    "SESSION_ID_LENGTH",
    "TemplateEngine",
    "WriterAgent",
    "_BATCH_SEMAPHORE",
    "_DETAILED_REVIEW_MAX_ITEMS",
    "_DETAILED_REVIEW_STORE",
    "_GRAPH",
    "_GraphQAReport",
    "_cache_detailed_review",
    "_count_report_issues",
    "_detailed_review_lock",
    "_execute_document_workflow",
    "_execute_via_graph",
    "_get_cached_detailed_review",
    "_get_error_code",
    "_get_graph",
    "_graph_lock",
    "_is_ralph_goal_met",
    "_run_ralph_loop",
    "_sanitize_error",
    "_sanitize_output_filename",
    "build_graph",
    "download_file",
    "get_detailed_review",
    "get_kb",
    "get_llm",
    "get_org_memory",
    "logger",
    "router",
    "run_batch",
    "run_in_executor",
    "run_meeting",
]
