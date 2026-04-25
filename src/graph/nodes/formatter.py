"""
format_document node — 包裝 TemplateEngine.parse_draft() + apply_template()
"""

import logging

from src.graph.state import GovDocState

logger = logging.getLogger(__name__)


def format_document(state: GovDocState) -> dict:
    """使用 Jinja2 模板格式化草稿為標準公文格式。

    讀取: draft, requirement
    寫入: formatted_draft, phase
    """
    try:
        from src.agents.template import TemplateEngine
        from src.core.models import PublicDocRequirement

        draft = state.get("draft", "")
        requirement_dict = state.get("requirement")
        if not draft:
            return {"error": "缺少草稿內容", "phase": "failed"}
        if not requirement_dict:
            return {"error": "缺少需求資料", "phase": "failed"}

        engine = TemplateEngine()
        req = PublicDocRequirement(**requirement_dict)

        sections = engine.parse_draft(draft)
        formatted = engine.apply_template(req, sections)

        return {
            "formatted_draft": formatted,
            "phase": "document_formatted",
        }

    except (ValueError, TypeError, AttributeError, KeyError, RuntimeError) as exc:
        logger.exception("format_document 失敗: %s", exc)
        return {"error": f"文件格式化失敗: {exc}", "phase": "failed"}
