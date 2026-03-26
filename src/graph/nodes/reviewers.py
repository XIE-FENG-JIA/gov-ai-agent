"""
reviewers — 5 個審查 node，各自包裝對應的審查 Agent。

每個 node 被 fan-out Send() 呼叫時，state 中會帶有 ``reviewer_name``
用以識別要執行哪個審查器。使用 ``_review_node`` decorator 統一
錯誤處理、結果序列化和降級回傳邏輯。
"""

import functools
import logging
from typing import Any, Callable

from src.graph.state import GovDocState

logger = logging.getLogger(__name__)


def _serialize_review_result(result: Any) -> dict[str, Any]:
    """將 ReviewResult pydantic model 轉為 dict。"""
    if hasattr(result, "model_dump"):
        return result.model_dump()
    # 相容 dict 格式（FormatAuditor 回傳 dict）
    return dict(result) if isinstance(result, dict) else {"raw": str(result)}


def _get_draft(state: GovDocState) -> str:
    """取得待審查的草稿：優先使用精煉版，否則格式化版，最後用原始草稿。"""
    return (
        state.get("refined_draft")
        or state.get("formatted_draft")
        or state.get("draft", "")
    )


def _review_node(agent_name: str) -> Callable:
    """Decorator：統一審查 node 的錯誤處理、序列化和降級回傳。

    被裝飾的函式只需回傳原始審查結果（ReviewResult 或 dict），
    decorator 自動包裝為 ``{"review_results": [...]}`` 格式。
    失敗時回傳帶 error 的降級結果，不中斷 LangGraph 流程。
    """
    def decorator(fn: Callable[[GovDocState], Any]) -> Callable[[GovDocState], dict]:
        @functools.wraps(fn)
        def wrapper(state: GovDocState) -> dict:
            try:
                result = fn(state)
                return {"review_results": [_serialize_review_result(result)]}
            except Exception as exc:
                logger.exception("%s 失敗: %s", agent_name, exc)
                return {
                    "review_results": [{
                        "agent_name": agent_name,
                        "issues": [],
                        "score": 0.0,
                        "confidence": 0.0,
                        "error": str(exc),
                    }]
                }
        return wrapper
    return decorator


# ────────────────────────────────────────────────────
# 1. Format Auditor
# ────────────────────────────────────────────────────

@_review_node("Format Auditor")
def review_format(state: GovDocState):
    """格式審查 node。"""
    from src.api.dependencies import get_llm, get_kb
    from src.agents.auditor import FormatAuditor
    from src.agents.review_parser import format_audit_to_review_result

    draft = _get_draft(state)
    doc_type = state.get("requirement", {}).get("doc_type", "函")
    auditor = FormatAuditor(get_llm(), get_kb())
    raw_result = auditor.audit(draft, doc_type)
    return format_audit_to_review_result(raw_result)


# ────────────────────────────────────────────────────
# 2. Style Checker
# ────────────────────────────────────────────────────

@_review_node("Style Checker")
def review_style(state: GovDocState):
    """文風審查 node。"""
    from src.api.dependencies import get_llm
    from src.agents.style_checker import StyleChecker

    draft = _get_draft(state)
    return StyleChecker(get_llm()).check(draft)


# ────────────────────────────────────────────────────
# 3. Fact Checker
# ────────────────────────────────────────────────────

@_review_node("Fact Checker")
def review_fact(state: GovDocState):
    """事實查核 node。"""
    from src.api.dependencies import get_llm
    from src.agents.fact_checker import FactChecker

    draft = _get_draft(state)
    doc_type = state.get("requirement", {}).get("doc_type", "函")

    law_verifier = None
    try:
        from src.knowledge.realtime_lookup import LawVerifier
        law_verifier = LawVerifier()
    except Exception as exc:
        logger.warning("LawVerifier 初始化失敗，略過即時法規驗證：%s", exc)

    return FactChecker(get_llm(), law_verifier=law_verifier).check(draft, doc_type=doc_type)


# ────────────────────────────────────────────────────
# 4. Consistency Checker
# ────────────────────────────────────────────────────

@_review_node("Consistency Checker")
def review_consistency(state: GovDocState):
    """一致性審查 node。"""
    from src.api.dependencies import get_llm
    from src.agents.consistency_checker import ConsistencyChecker

    return ConsistencyChecker(get_llm()).check(_get_draft(state))


# ────────────────────────────────────────────────────
# 5. Compliance Checker
# ────────────────────────────────────────────────────

@_review_node("Compliance Checker")
def review_compliance(state: GovDocState):
    """合規審查 node。"""
    from src.api.dependencies import get_llm, get_kb
    from src.agents.compliance_checker import ComplianceChecker

    draft = _get_draft(state)
    llm, kb = get_llm(), get_kb()

    policy_fetcher = None
    try:
        from src.knowledge.realtime_lookup import RecentPolicyFetcher
        policy_fetcher = RecentPolicyFetcher()
    except Exception as exc:
        logger.warning("RecentPolicyFetcher 初始化失敗，略過即時政策查詢：%s", exc)

    return ComplianceChecker(llm, kb, policy_fetcher=policy_fetcher).check(draft)
