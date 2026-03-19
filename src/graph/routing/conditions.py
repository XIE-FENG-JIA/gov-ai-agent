"""
conditions — LangGraph 條件邊函式
==================================

提供 should_review、should_refine、fan_out_reviewers 等
用於 StateGraph conditional_edge 的判斷函式。
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.types import Send

from src.graph.state import GovDocState
from src.graph.routing.review_selector import select_review_agents

logger = logging.getLogger(__name__)

# 預設最大精煉輪次
DEFAULT_MAX_REFINEMENT_ROUNDS = 2


def should_review(state: GovDocState) -> str:
    """判斷是否進入審查流程。

    條件邊：format_document 之後
    - 若 review_requested == False 或有 error → 直接跳到 export
    - 否則 → 進入 init_review（啟動 fan-out）

    Returns:
        "init_review" 或 "export_docx"
    """
    # 有錯誤時直接匯出（降級模式）
    if state.get("error"):
        logger.warning("should_review: 偵測到錯誤，跳過審查直接匯出")
        return "export_docx"

    # 使用者可選擇跳過審查
    if state.get("review_requested") is False:
        logger.info("should_review: 使用者選擇跳過審查")
        return "export_docx"

    return "init_review"


def should_refine(state: GovDocState) -> str:
    """判斷是否需要精煉草稿。

    條件邊：aggregate_reviews 之後
    - 若 risk 為 Safe/Low → 直接到 build_report
    - 若已達最大精煉輪次 → build_report
    - 否則 → refine_draft

    Returns:
        "refine_draft" 或 "build_report"
    """
    report: dict[str, Any] = state.get("aggregated_report", {})
    risk = report.get("risk_summary", "Unknown")
    current_round = state.get("refinement_round", 0)
    max_rounds = state.get("max_refinement_rounds", DEFAULT_MAX_REFINEMENT_ROUNDS)

    # 品質達標
    if risk in ("Safe", "Low"):
        logger.info("should_refine: 品質達標 (risk=%s)，跳過精煉", risk)
        return "build_report"

    # 達到精煉上限
    if current_round >= max_rounds:
        logger.info(
            "should_refine: 已達精煉上限 (%d/%d)，停止精煉",
            current_round, max_rounds,
        )
        return "build_report"

    # 全部 Agent 失敗
    agent_results = report.get("agent_results", [])
    if agent_results and all(r.get("confidence", 1.0) == 0.0 for r in agent_results):
        logger.warning("should_refine: 所有 Agent 失敗，跳過精煉")
        return "build_report"

    logger.info(
        "should_refine: 需要精煉 (risk=%s, round=%d/%d)",
        risk, current_round, max_rounds,
    )
    return "refine_draft"


def fan_out_reviewers(state: GovDocState) -> list[Send]:
    """產生 Send() 清單，將審查任務並行分發到各審查 node。

    用於 conditional_edges：init_review → [Send("review_format", state), ...]

    Returns:
        Send 物件清單，每個對應一個審查 node
    """
    doc_type = state.get("requirement", {}).get("doc_type", "函")

    # 選取應啟用的審查 Agent
    selected = select_review_agents(doc_type)

    sends = []
    for node_name in selected:
        # Send() 會將整個 state 傳給目標 node
        sends.append(Send(node_name, state))

    logger.info(
        "fan_out_reviewers: 分發 %d 個審查任務 → %s",
        len(sends), selected,
    )
    return sends
