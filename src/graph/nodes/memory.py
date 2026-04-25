"""
fetch_org_memory node — 包裝 OrganizationalMemory.get_writing_hints()
"""

import logging

from src.graph.state import GovDocState

logger = logging.getLogger(__name__)


def fetch_org_memory(state: GovDocState) -> dict:
    """查詢機構記憶，取得該機關的寫作偏好提示。

    讀取: requirement (需要 sender 欄位)
    寫入: org_hints, phase
    """
    try:
        from src.api.dependencies import get_org_memory

        requirement = state.get("requirement", {})
        sender = requirement.get("sender", "")

        org_memory = get_org_memory()
        if org_memory and sender:
            hints = org_memory.get_writing_hints(sender)
        else:
            hints = ""

        return {
            "org_hints": hints,
            "phase": "memory_fetched",
        }

    except (OSError, ValueError, AttributeError, TypeError, RuntimeError) as exc:
        logger.exception("fetch_org_memory 失敗: %s", exc)
        # 機構記憶失敗不阻斷流程，只記錄警告
        return {"org_hints": "", "phase": "memory_fetched"}
