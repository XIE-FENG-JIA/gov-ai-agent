"""
LangGraph 公文生成流程圖 — 頂層套件
====================================

提供 ``build_graph()`` 工廠函式，回傳編譯後的 StateGraph。
"""

from src.graph.builder import build_graph

__all__ = ["build_graph"]
