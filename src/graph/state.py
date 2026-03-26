"""
GovDocState — LangGraph 狀態定義
=================================

使用 TypedDict + Annotated reducer 定義整個公文生成流程的共享狀態。
``review_results`` 使用自訂 reducer，支援並行審查結果合併及精煉輪次間的重設。
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict


def _review_results_reducer(
    current: list[dict[str, Any]],
    update: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """自訂 reducer：空 list 表示重設（由 _init_review 觸發），否則串接。

    解決 operator.add 無法清空 list 的問題——精煉迴圈重新進入
    init_review 時需清除上一輪審查結果，避免舊 issues 疊加導致
    risk 評估偏高與不必要的額外精煉。
    """
    if not update:
        return []
    return (current or []) + update


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
    # 自訂 reducer：並行審查結果串接，空 list 觸發重設（精煉迴圈用）
    review_results: Annotated[list[dict[str, Any]], _review_results_reducer]
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
