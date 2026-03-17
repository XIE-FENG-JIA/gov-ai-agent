"""
健康檢查與效能監控路由
======================
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.core.constants import API_VERSION, API_MAX_WORKERS
from src.api.dependencies import get_config, get_raw_kb, get_raw_llm
from src.api.helpers import run_in_executor
import src.api.middleware as _mw
from src.api.middleware import _RATE_LIMIT_RPM

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", tags=["健康檢查"])
async def root() -> dict[str, str]:
    """基本健康檢查

    回傳伺服器狀態、API 版本號及時間戳記。
    """
    return {
        "status": "healthy",
        "service": "公文 AI Agent API",
        "version": API_VERSION,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/api/v1/health", tags=["健康檢查"])
async def health_check():
    """詳細健康檢查

    回傳 LLM 提供者、模型資訊與各依賴元件狀態（不洩漏檔案路徑等敏感資訊）。
    各元件狀態：available / degraded / unavailable。
    整體狀態：healthy（全部 available）/ degraded（部分可用）/ unhealthy（全部不可用）。
    非 healthy 時回傳 HTTP 503。
    """
    config = get_config()
    llm_config = config.get("llm", {})

    _kb = get_raw_kb()
    _llm = get_raw_llm()

    # 檢查知識庫狀態
    kb_status = "unavailable"
    kb_collections = 0
    if _kb is not None:
        if not _kb.is_available or _kb.client is None:
            kb_status = "degraded"
        else:
            kb_status = "available"
            try:
                kb_collections = len(_kb.client.list_collections())
            except Exception as e:
                logger.warning("KB health check 失敗: %s", e)
                kb_status = "degraded"

    # 檢查 LLM 連線（5 秒逾時）
    _HEALTH_TIMEOUT = 5
    llm_status = "unavailable"
    if _llm is not None:
        try:
            llm_result = await run_in_executor(
                lambda: _llm.generate("ping"), timeout=_HEALTH_TIMEOUT,
            )
            llm_status = "available" if llm_result else "degraded"
        except Exception as e:
            logger.warning("LLM health check 失敗: %s", e)
            llm_status = "unavailable"

    # 檢查 embedding 模型（5 秒逾時）
    embedding_status = "unavailable"
    if _llm is not None:
        try:
            embed_result = await run_in_executor(
                lambda: _llm.embed("test"), timeout=_HEALTH_TIMEOUT,
            )
            embedding_status = "available" if embed_result else "degraded"
        except Exception as e:
            logger.warning("Embedding health check 失敗: %s", e)
            embedding_status = "unavailable"

    # 判定整體狀態
    component_statuses = [kb_status, llm_status, embedding_status]
    if all(s == "available" for s in component_statuses):
        overall_status = "healthy"
    elif all(s == "unavailable" for s in component_statuses):
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"

    body = {
        "status": overall_status,
        "version": API_VERSION,
        "llm_provider": llm_config.get("provider", "unknown"),
        "llm_model": llm_config.get("model", "unknown"),
        "kb_status": kb_status,
        "kb_collections": kb_collections,
        "llm_status": llm_status,
        "embedding_status": embedding_status,
        "rate_limit_rpm": _RATE_LIMIT_RPM,
        "auth_enabled": config.get("api", {}).get("auth_enabled", False),
    }

    if overall_status != "healthy":
        return JSONResponse(content=body, status_code=503)
    return body


@router.get("/api/v1/metrics", tags=["效能監控"])
async def get_metrics() -> dict[str, Any]:
    """效能監控指標

    回傳伺服器的即時效能指標，包含請求統計、平均回應時間、
    活動請求數及快取命中率。
    """
    data = _mw.metrics.snapshot()
    data["executor_max_workers"] = API_MAX_WORKERS
    return data
