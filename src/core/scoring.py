"""
評分與風險判定模組（純函式）

從 EditorInChief 抽出的加權分數計算和風險評估邏輯，
確保 scoring 邏輯可被 graph workflow 和其他模組獨立使用。

所有函式皆為純函式（無 self、無副作用）。
"""

from src.core.constants import (
    CATEGORY_WEIGHTS,
    WARNING_WEIGHT_FACTOR,
    assess_risk_level,
)
from src.core.review_models import ReviewResult


def get_agent_category(agent_name: str) -> str:
    """推斷 Agent 所屬的類別以取得對應權重。

    Args:
        agent_name: Agent 名稱（如 "Format Auditor", "Style Checker"）

    Returns:
        類別字串，用於查詢 CATEGORY_WEIGHTS
    """
    name_lower = agent_name.lower()
    if "format" in name_lower or "auditor" in name_lower:
        return "format"
    elif "compliance" in name_lower or "policy" in name_lower:
        return "compliance"
    elif "fact" in name_lower or "citation" in name_lower:
        return "fact"
    elif "consistency" in name_lower:
        return "consistency"
    return "style"  # 預設為最低權重


def calculate_weighted_scores(
    results: list[ReviewResult],
) -> tuple[float, float]:
    """計算加權品質分數。

    根據每個 Agent 的類別權重和信心度，計算加權總分和總權重。

    Args:
        results: 所有審查結果

    Returns:
        (weighted_score, total_weight) 元組
    """
    weighted_score = 0.0
    total_weight = 0.0

    for res in results:
        agent_category = get_agent_category(res.agent_name)
        weight = CATEGORY_WEIGHTS.get(agent_category, 1.0)
        weighted_score += res.score * weight * res.confidence
        total_weight += weight * res.confidence

    return weighted_score, total_weight


def calculate_risk_scores(
    results: list[ReviewResult],
) -> tuple[float, float]:
    """計算加權風險分數（錯誤和警告）。

    遍歷所有審查結果的 issues，根據類別權重累加
    error 和 warning 的加權分數。

    Args:
        results: 所有審查結果

    Returns:
        (weighted_error_score, weighted_warning_score) 元組
    """
    weighted_error_score = 0.0
    weighted_warning_score = 0.0

    for res in results:
        agent_category = get_agent_category(res.agent_name)
        weight = CATEGORY_WEIGHTS.get(agent_category, 1.0)

        for issue in res.issues:
            if issue.severity == "error":
                weighted_error_score += weight
            elif issue.severity == "warning":
                weighted_warning_score += weight * WARNING_WEIGHT_FACTOR

    return weighted_error_score, weighted_warning_score


# 重新匯出，方便從 scoring 模組統一取用
__all__ = [
    "CATEGORY_WEIGHTS",
    "assess_risk_level",
    "get_agent_category",
    "calculate_weighted_scores",
    "calculate_risk_scores",
]
