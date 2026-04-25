"""
aggregate_reviews node — 匯總所有審查結果

評分邏輯委派給 ``src.core.scoring`` 共用模組，
確保 LangGraph pipeline 和 EditorInChief 使用一致的加權公式。
"""

import logging
from typing import Any

from src.graph.state import GovDocState
from src.core.constants import assess_risk_level
from src.core.review_models import ReviewResult, ReviewIssue
from src.core.scoring import calculate_weighted_scores, calculate_risk_scores

logger = logging.getLogger(__name__)


def _dicts_to_review_results(raw: list[dict[str, Any]]) -> list[ReviewResult]:
    """將 LangGraph state 中的 dict 清單轉為 ReviewResult model。

    對於格式不完整的 dict，使用安全預設值避免阻斷流程。
    """
    results: list[ReviewResult] = []
    for d in raw:
        try:
            issues = []
            for iss in d.get("issues", []):
                if isinstance(iss, dict):
                    issues.append(ReviewIssue(**iss))
                elif isinstance(iss, ReviewIssue):
                    issues.append(iss)
            results.append(ReviewResult(
                agent_name=d.get("agent_name", "Unknown"),
                issues=issues,
                score=d.get("score", 0.0),
                confidence=d.get("confidence", 1.0),
            ))
        except (TypeError, KeyError, ValueError) as exc:
            logger.warning("無法轉換審查結果 dict → ReviewResult: %s", exc)
            results.append(ReviewResult(
                agent_name=d.get("agent_name", "Unknown"),
                issues=[],
                score=d.get("score", 0.0),
                confidence=d.get("confidence", 1.0),
            ))
    return results


def aggregate_reviews(state: GovDocState) -> dict:
    """匯總並行審查結果，計算加權分數與風險等級。

    讀取: review_results
    寫入: aggregated_report, phase
    """
    try:
        review_results: list[dict[str, Any]] = state.get("review_results", [])

        if not review_results:
            return {
                "aggregated_report": {
                    "overall_score": 1.0,
                    "risk_summary": "Safe",
                    "agent_results": [],
                    "error_count": 0,
                    "warning_count": 0,
                },
                "phase": "reviews_aggregated",
            }

        # dict → ReviewResult model，以便呼叫共用評分函式
        models = _dicts_to_review_results(review_results)

        # 使用 src.core.scoring 的共用函式計算加權分數
        weighted_score, total_weight = calculate_weighted_scores(models)
        weighted_error_score, weighted_warning_score = calculate_risk_scores(models)

        avg_score = weighted_score / total_weight if total_weight > 0 else 0.0

        if total_weight == 0.0:
            risk = "Critical"
        else:
            risk = assess_risk_level(weighted_error_score, weighted_warning_score, avg_score)

        # 計算 error/warning 計數（報告用）
        error_count = sum(
            1 for r in models for i in r.issues if i.severity == "error"
        )
        warning_count = sum(
            1 for r in models for i in r.issues if i.severity == "warning"
        )

        report = {
            "overall_score": round(avg_score, 4),
            "risk_summary": risk,
            "agent_results": review_results,
            "error_count": error_count,
            "warning_count": warning_count,
            "weighted_error_score": round(weighted_error_score, 2),
            "weighted_warning_score": round(weighted_warning_score, 2),
        }

        return {
            "aggregated_report": report,
            "phase": "reviews_aggregated",
        }

    except (RuntimeError, AttributeError, TypeError, ZeroDivisionError) as exc:
        logger.exception("aggregate_reviews 失敗: %s", exc)
        return {
            "aggregated_report": {
                "overall_score": 0.0,
                "risk_summary": "Critical",
                "error": str(exc),
            },
            "error": f"審查彙整失敗: {exc}",
            "phase": "failed",
        }
