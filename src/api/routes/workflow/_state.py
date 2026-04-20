"""
workflow package 的共享狀態與快取。
"""

import asyncio
import logging
import os
import threading
from typing import Any

from fastapi import APIRouter

from src.graph import build_graph

logger = logging.getLogger(__name__)

router = APIRouter()

_BATCH_SEMAPHORE = asyncio.Semaphore(3)

_GRAPH = None
_graph_lock = threading.Lock()

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
