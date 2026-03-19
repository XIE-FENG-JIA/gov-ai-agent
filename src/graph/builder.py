"""
build_graph() — 組裝完整的 LangGraph StateGraph
=================================================

流程概覽::

    parse_requirement → fetch_org_memory → write_draft → format_document
        ↓ (should_review)
    init_review → fan_out_reviewers → [review_format, review_style, ...]
        ↓ (所有審查完成後自動匯合)
    aggregate_reviews
        ↓ (should_refine)
    refine_draft → init_review (迴圈)
        或
    build_report → export_docx → END
"""

import logging

from langgraph.graph import StateGraph, END

from src.graph.state import GovDocState
from src.graph.nodes.requirement import parse_requirement
from src.graph.nodes.memory import fetch_org_memory
from src.graph.nodes.writer import write_draft
from src.graph.nodes.formatter import format_document
from src.graph.nodes.reviewers import (
    review_format,
    review_style,
    review_fact,
    review_consistency,
    review_compliance,
)
from src.graph.nodes.aggregator import aggregate_reviews
from src.graph.nodes.refiner import refine_draft
from src.graph.nodes.reporter import build_report
from src.graph.nodes.exporter import export_docx
from src.graph.routing.conditions import (
    should_review,
    should_refine,
    fan_out_reviewers,
)

logger = logging.getLogger(__name__)


def _init_review(state: GovDocState) -> dict:
    """初始化審查流程的 passthrough node。

    清空上一輪的 review_results，以免 reducer 疊加舊資料。
    """
    return {"review_results": [], "phase": "reviewing"}


def build_graph() -> StateGraph:
    """建構並回傳編譯後的公文生成 LangGraph。

    Returns:
        已編譯的 StateGraph（可直接 ``.invoke()`` 或 ``.stream()``）
    """
    graph = StateGraph(GovDocState)

    # ── 註冊 Node ──────────────────────────────────────
    graph.add_node("parse_requirement", parse_requirement)
    graph.add_node("fetch_org_memory", fetch_org_memory)
    graph.add_node("write_draft", write_draft)
    graph.add_node("format_document", format_document)
    graph.add_node("init_review", _init_review)
    graph.add_node("review_format", review_format)
    graph.add_node("review_style", review_style)
    graph.add_node("review_fact", review_fact)
    graph.add_node("review_consistency", review_consistency)
    graph.add_node("review_compliance", review_compliance)
    graph.add_node("aggregate_reviews", aggregate_reviews)
    graph.add_node("refine_draft", refine_draft)
    graph.add_node("build_report", build_report)
    graph.add_node("export_docx", export_docx)

    # ── 入口 ──────────────────────────────────────────
    graph.set_entry_point("parse_requirement")

    # ── 線性邊（前四步） ────────────────────────────────
    graph.add_edge("parse_requirement", "fetch_org_memory")
    graph.add_edge("fetch_org_memory", "write_draft")
    graph.add_edge("write_draft", "format_document")

    # ── 條件邊：是否進入審查 ─────────────────────────────
    graph.add_conditional_edges(
        "format_document",
        should_review,
        {
            "init_review": "init_review",
            "export_docx": "export_docx",
        },
    )

    # ── 並行 fan-out：init_review → Send() 到各審查 node ─
    graph.add_conditional_edges(
        "init_review",
        fan_out_reviewers,
        # Send() 直接指定目標 node，此處不需要 path_map
    )

    # ── 各審查 node → aggregate_reviews ───────────────
    graph.add_edge("review_format", "aggregate_reviews")
    graph.add_edge("review_style", "aggregate_reviews")
    graph.add_edge("review_fact", "aggregate_reviews")
    graph.add_edge("review_consistency", "aggregate_reviews")
    graph.add_edge("review_compliance", "aggregate_reviews")

    # ── 條件邊：是否精煉 ─────────────────────────────────
    graph.add_conditional_edges(
        "aggregate_reviews",
        should_refine,
        {
            "refine_draft": "refine_draft",
            "build_report": "build_report",
        },
    )

    # ── 精煉迴圈：refine → 重新審查 ──────────────────────
    graph.add_edge("refine_draft", "init_review")

    # ── 結束流程 ──────────────────────────────────────
    graph.add_edge("build_report", "export_docx")
    graph.add_edge("export_docx", END)

    # ── 編譯並回傳 ────────────────────────────────────
    logger.info("LangGraph 公文生成流程圖已建構完成")
    compiled = graph.compile()

    return compiled
