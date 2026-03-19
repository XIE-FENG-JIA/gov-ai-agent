"""
aggregate_reviews node — 匯總所有審查結果
"""

import logging
from typing import Any

from src.graph.state import GovDocState
from src.core.constants import CATEGORY_WEIGHTS, WARNING_WEIGHT_FACTOR, assess_risk_level

logger = logging.getLogger(__name__)


def _get_agent_category(agent_name: str) -> str:
    """推斷 Agent 所屬的類別以取得對應權重。"""
    name_lower = agent_name.lower()
    if "format" in name_lower or "auditor" in name_lower:
        return "format"
    if "compliance" in name_lower or "policy" in name_lower:
        return "compliance"
    if "fact" in name_lower:
        return "fact"
    if "consistency" in name_lower:
        return "consistency"
    return "style"


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

        # 計算加權分數
        weighted_score = 0.0
        total_weight = 0.0
        weighted_error_score = 0.0
        weighted_warning_score = 0.0
        error_count = 0
        warning_count = 0

        for res in review_results:
            agent_name = res.get("agent_name", "Unknown")
            score = res.get("score", 0.0)
            confidence = res.get("confidence", 1.0)
            issues = res.get("issues", [])

            category = _get_agent_category(agent_name)
            weight = CATEGORY_WEIGHTS.get(category, 1.0)

            weighted_score += score * weight * confidence
            total_weight += weight * confidence

            for issue in issues:
                severity = issue.get("severity", "info")
                if severity == "error":
                    weighted_error_score += weight
                    error_count += 1
                elif severity == "warning":
                    weighted_warning_score += weight * WARNING_WEIGHT_FACTOR
                    warning_count += 1

        avg_score = weighted_score / total_weight if total_weight > 0 else 0.0

        if total_weight == 0.0:
            risk = "Critical"
        else:
            risk = assess_risk_level(weighted_error_score, weighted_warning_score, avg_score)

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

    except Exception as exc:
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
