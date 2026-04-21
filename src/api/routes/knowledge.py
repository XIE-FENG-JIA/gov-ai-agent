"""
知識庫搜尋路由
==============
"""

import logging

from fastapi import APIRouter, Depends

from src.api.auth import require_api_key
from src.api.dependencies import get_kb
from src.api.helpers import _sanitize_error, _get_error_code, run_in_executor
from src.api.models import KBSearchRequest, KBSearchResponse

logger = logging.getLogger(__name__)

router = APIRouter()
WRITE_AUTH = [Depends(require_api_key)]


@router.post(
    "/api/v1/kb/search",
    response_model=KBSearchResponse,
    tags=["知識庫"],
    dependencies=WRITE_AUTH,
)
async def kb_search(request: KBSearchRequest) -> KBSearchResponse:
    """知識庫語意搜尋

    在知識庫中搜尋與查詢語意相近的範例、法規與政策文件。
    """
    try:
        kb = get_kb()

        results = await run_in_executor(
            lambda: kb.search_hybrid(
                query=request.query,
                n_results=request.n_results,
                source_level=request.source_level,
                doc_type=request.doc_type,
            )
        )

        return KBSearchResponse(success=True, results=results)

    except Exception as e:
        logger.exception("知識庫搜尋失敗")
        return KBSearchResponse(success=False, error=_sanitize_error(e), error_code=_get_error_code(e))
