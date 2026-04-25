"""
parse_requirement node — 包裝 RequirementAgent.analyze()
"""

import logging

from src.core.llm import LLMError
from src.graph.state import GovDocState

logger = logging.getLogger(__name__)


def parse_requirement(state: GovDocState) -> dict:
    """解析使用者輸入，回傳結構化的公文需求。

    讀取: user_input
    寫入: requirement, phase
    """
    try:
        from src.api.dependencies import get_llm
        from src.agents.requirement import RequirementAgent

        user_input = state.get("user_input", "")
        if not user_input:
            return {"error": "使用者輸入為空", "phase": "failed"}

        llm = get_llm()
        agent = RequirementAgent(llm)
        req = agent.analyze(user_input)

        # 序列化 Pydantic model → dict
        return {
            "requirement": req.model_dump(),
            "phase": "requirement_parsed",
        }

    except (LLMError, OSError, ValueError, RuntimeError) as exc:
        logger.exception("parse_requirement 失敗: %s", exc)
        return {"error": f"需求分析失敗: {exc}", "phase": "failed"}
