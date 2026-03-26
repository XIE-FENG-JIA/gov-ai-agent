"""
reviewers — 5 個審查 node，各自包裝對應的審查 Agent。

每個 node 被 fan-out Send() 呼叫時，state 中會帶有 ``reviewer_name``
用以識別要執行哪個審查器。但這裡直接定義 5 個獨立函式，
各自回傳 ``review_results`` 清單（會由 operator.add reducer 合併）。
"""

import logging
from typing import Any

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


# ────────────────────────────────────────────────────
# 1. Format Auditor
# ────────────────────────────────────────────────────

def review_format(state: GovDocState) -> dict:
    """格式審查 node。

    讀取: draft/formatted_draft/refined_draft, requirement
    寫入: review_results (list, reducer=add)
    """
    try:
        from src.api.dependencies import get_llm, get_kb
        from src.agents.auditor import FormatAuditor
        from src.agents.review_parser import format_audit_to_review_result

        draft = _get_draft(state)
        doc_type = state.get("requirement", {}).get("doc_type", "函")

        llm = get_llm()
        kb = get_kb()
        auditor = FormatAuditor(llm, kb)

        raw_result = auditor.audit(draft, doc_type)
        review_result = format_audit_to_review_result(raw_result)

        return {"review_results": [_serialize_review_result(review_result)]}

    except Exception as exc:
        logger.exception("review_format 失敗: %s", exc)
        return {
            "review_results": [{
                "agent_name": "Format Auditor",
                "issues": [],
                "score": 0.0,
                "confidence": 0.0,
                "error": str(exc),
            }]
        }


# ────────────────────────────────────────────────────
# 2. Style Checker
# ────────────────────────────────────────────────────

def review_style(state: GovDocState) -> dict:
    """文風審查 node。

    讀取: draft/formatted_draft/refined_draft
    寫入: review_results
    """
    try:
        from src.api.dependencies import get_llm
        from src.agents.style_checker import StyleChecker

        draft = _get_draft(state)
        llm = get_llm()
        checker = StyleChecker(llm)
        result = checker.check(draft)

        return {"review_results": [_serialize_review_result(result)]}

    except Exception as exc:
        logger.exception("review_style 失敗: %s", exc)
        return {
            "review_results": [{
                "agent_name": "Style Checker",
                "issues": [],
                "score": 0.0,
                "confidence": 0.0,
                "error": str(exc),
            }]
        }


# ────────────────────────────────────────────────────
# 3. Fact Checker
# ────────────────────────────────────────────────────

def review_fact(state: GovDocState) -> dict:
    """事實查核 node。

    讀取: draft/formatted_draft/refined_draft, requirement
    寫入: review_results
    """
    try:
        from src.api.dependencies import get_llm
        from src.agents.fact_checker import FactChecker

        draft = _get_draft(state)
        doc_type = state.get("requirement", {}).get("doc_type", "函")
        llm = get_llm()

        # 嘗試初始化即時法規驗證
        law_verifier = None
        try:
            from src.knowledge.realtime_lookup import LawVerifier
            law_verifier = LawVerifier()
        except Exception as exc:
            logger.warning("LawVerifier 初始化失敗，略過即時法規驗證：%s", exc)

        checker = FactChecker(llm, law_verifier=law_verifier)
        result = checker.check(draft, doc_type=doc_type)

        return {"review_results": [_serialize_review_result(result)]}

    except Exception as exc:
        logger.exception("review_fact 失敗: %s", exc)
        return {
            "review_results": [{
                "agent_name": "Fact Checker",
                "issues": [],
                "score": 0.0,
                "confidence": 0.0,
                "error": str(exc),
            }]
        }


# ────────────────────────────────────────────────────
# 4. Consistency Checker
# ────────────────────────────────────────────────────

def review_consistency(state: GovDocState) -> dict:
    """一致性審查 node。

    讀取: draft/formatted_draft/refined_draft
    寫入: review_results
    """
    try:
        from src.api.dependencies import get_llm
        from src.agents.consistency_checker import ConsistencyChecker

        draft = _get_draft(state)
        llm = get_llm()
        checker = ConsistencyChecker(llm)
        result = checker.check(draft)

        return {"review_results": [_serialize_review_result(result)]}

    except Exception as exc:
        logger.exception("review_consistency 失敗: %s", exc)
        return {
            "review_results": [{
                "agent_name": "Consistency Checker",
                "issues": [],
                "score": 0.0,
                "confidence": 0.0,
                "error": str(exc),
            }]
        }


# ────────────────────────────────────────────────────
# 5. Compliance Checker
# ────────────────────────────────────────────────────

def review_compliance(state: GovDocState) -> dict:
    """合規審查 node。

    讀取: draft/formatted_draft/refined_draft
    寫入: review_results
    """
    try:
        from src.api.dependencies import get_llm, get_kb
        from src.agents.compliance_checker import ComplianceChecker

        draft = _get_draft(state)
        llm = get_llm()
        kb = get_kb()

        # 嘗試初始化即時政策查詢
        policy_fetcher = None
        try:
            from src.knowledge.realtime_lookup import RecentPolicyFetcher
            policy_fetcher = RecentPolicyFetcher()
        except Exception as exc:
            logger.warning("RecentPolicyFetcher 初始化失敗，略過即時政策查詢：%s", exc)

        checker = ComplianceChecker(llm, kb, policy_fetcher=policy_fetcher)
        result = checker.check(draft)

        return {"review_results": [_serialize_review_result(result)]}

    except Exception as exc:
        logger.exception("review_compliance 失敗: %s", exc)
        return {
            "review_results": [{
                "agent_name": "Compliance Checker",
                "issues": [],
                "score": 0.0,
                "confidence": 0.0,
                "error": str(exc),
            }]
        }
