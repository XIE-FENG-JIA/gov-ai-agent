"""
write_draft node — 包裝 WriterAgent.write_draft()
"""

import logging

from src.graph.state import GovDocState

logger = logging.getLogger(__name__)


def write_draft(state: GovDocState) -> dict:
    """使用 RAG 產生公文草稿。

    讀取: requirement, org_hints
    寫入: draft, phase
    """
    try:
        from src.api.dependencies import get_llm, get_kb
        from src.agents.writer import WriterAgent
        from src.core.models import PublicDocRequirement

        requirement_dict = state.get("requirement")
        if not requirement_dict:
            return {"error": "缺少需求資料", "phase": "failed"}

        llm = get_llm()
        kb = get_kb()
        agent = WriterAgent(llm, kb)

        # 從 dict 重建 Pydantic model
        req = PublicDocRequirement(**requirement_dict)

        draft = agent.write_draft(req)

        return {
            "draft": draft,
            "phase": "draft_written",
        }

    except Exception as exc:
        logger.exception("write_draft 失敗: %s", exc)
        return {"error": f"草稿撰寫失敗: {exc}", "phase": "failed"}
