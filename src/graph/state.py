"""
GovDocState — LangGraph 狀態定義
=================================

使用 TypedDict + Annotated reducer 定義整個公文生成流程的共享狀態。
``review_results`` 使用 ``operator.add`` reducer，
讓並行審查 node 的結果自動合併。
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class GovDocState(TypedDict, total=False):
    """公文 AI Agent 的 LangGraph 狀態。

    所有欄位皆 ``total=False``，允許部分初始化。
    """

    # ── 輸入 ──────────────────────────────────────────
    user_input: str  # 使用者的原始需求描述

    # ── 需求分析 ──────────────────────────────────────
    requirement: dict[str, Any]  # PublicDocRequirement 序列化後的 dict

    # ── 機構記憶 ──────────────────────────────────────
    org_hints: str  # OrganizationalMemory 回傳的寫作提示

    # ── 草稿 ──────────────────────────────────────────
    draft: str  # WriterAgent 產生的 Markdown 草稿
    formatted_draft: str  # TemplateEngine 格式化後的公文

    # ── 審查 ──────────────────────────────────────────
    review_requested: bool  # 是否啟用審查流程
    # 使用 operator.add reducer：並行 Send() 的審查結果會自動合併
    review_results: Annotated[list[dict[str, Any]], operator.add]
    aggregated_report: dict[str, Any]  # aggregate_reviews 產出的彙整報告

    # ── 審查用臨時欄位 ────────────────────────────────
    reviewer_name: str  # fan-out Send() 帶入的審查者名稱

    # ── 精煉 ──────────────────────────────────────────
    refined_draft: str  # 經過修正的草稿
    refinement_round: int  # 目前精煉輪次
    max_refinement_rounds: int  # 最大精煉輪次

    # ── 報告與匯出 ─────────────────────────────────────
    report: str  # Markdown 品質報告
    output_path: str  # 匯出的 .docx 路徑

    # ── 控制 ──────────────────────────────────────────
    phase: str  # 目前階段標記（便於 debug）
    error: str  # 錯誤訊息（非空表示流程異常）
