"""Web UI 請求處理工具 — 從 app.py 拆出的輸入驗證與 payload 建構。"""
from __future__ import annotations

import re as _re

from src.core.constants import MAX_USER_INPUT_LENGTH
from src.core.models import VALID_DOC_TYPES


def _prepare_generate_input(
    user_input: str,
    doc_type: str,
) -> tuple[str | None, str | None]:
    """驗證並準備生成輸入。回傳 (error, effective_input)；其中一定有一個為 None。"""
    stripped = user_input.strip()
    if len(stripped) < 5:
        return "需求描述至少需要 5 個字。", None
    if len(stripped) > MAX_USER_INPUT_LENGTH:
        return (
            f"需求描述不可超過 {MAX_USER_INPUT_LENGTH} 字（目前 {len(stripped)} 字）。",
            None,
        )
    effective = (
        f"[公文類型：{doc_type}] {stripped}"
        if (doc_type and doc_type in VALID_DOC_TYPES)
        else stripped
    )
    return None, effective


def _build_meeting_payload(
    effective_input: str,
    skip_review: bool,
    ralph_loop: bool,
    ralph_max_cycles: int,
    ralph_target_score: float,
) -> tuple[dict, float]:
    """建構 meeting API 的 payload 與逾時秒數。回傳 (payload, timeout)。"""
    meeting_timeout = 600.0 if (not skip_review and ralph_loop) else 180.0
    payload: dict = {
        "user_input": effective_input,
        "skip_review": skip_review,
        "output_docx": True,
    }
    if not skip_review:
        payload["ralph_loop"] = ralph_loop
        if ralph_loop:
            payload.update({
                "use_graph": False,
                "max_rounds": 2,
                "ralph_max_cycles": ralph_max_cycles,
                "ralph_target_score": ralph_target_score,
            })
    return payload, meeting_timeout


def _check_session_id(session_id: str) -> str | None:
    """驗證 session_id 格式。回傳錯誤訊息，或 None（若有效）。"""
    if not session_id:
        return "缺少 session_id 參數"
    if not _re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", session_id):
        return "session_id 格式無效"
    return None
