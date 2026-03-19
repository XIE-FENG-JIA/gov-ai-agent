"""
review_selector — 審查 Agent 選取策略
======================================

定義 REVIEW_AGENT_PROFILES 和 select_review_agents()，
根據公文類型和設定決定啟用哪些審查 Agent。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# 審查 Agent 的 profile 定義
# key = node 函式名稱（與 builder.py 中的 node 名稱對應）
REVIEW_AGENT_PROFILES: dict[str, dict[str, Any]] = {
    "review_format": {
        "display_name": "Format Auditor",
        "description": "格式審查：檢查公文結構完整性、段落編號、必要欄位",
        "category": "format",
        "priority": 1,  # 數字越小越優先
        "always_run": True,  # 所有公文類型都執行
        "applicable_doc_types": None,  # None = 適用所有類型
    },
    "review_style": {
        "display_name": "Style Checker",
        "description": "文風審查：檢查語氣、用詞正式度、敬語使用",
        "category": "style",
        "priority": 2,
        "always_run": True,
        "applicable_doc_types": None,
    },
    "review_fact": {
        "display_name": "Fact Checker",
        "description": "事實查核：驗證法規引用、日期邏輯、數字一致性",
        "category": "fact",
        "priority": 3,
        "always_run": True,
        "applicable_doc_types": None,
    },
    "review_consistency": {
        "display_name": "Consistency Checker",
        "description": "一致性審查：檢查主旨與內容、各段落間的邏輯一致性",
        "category": "consistency",
        "priority": 4,
        "always_run": True,
        "applicable_doc_types": None,
    },
    "review_compliance": {
        "display_name": "Compliance Checker",
        "description": "合規審查：檢查是否符合最新政策方針與上級指示",
        "category": "compliance",
        "priority": 5,
        "always_run": False,  # 可依設定關閉
        "applicable_doc_types": None,
    },
}


def select_review_agents(
    doc_type: str = "函",
    *,
    skip_compliance: bool = False,
    enabled_agents: list[str] | None = None,
) -> list[str]:
    """根據公文類型和設定，回傳應啟用的審查 Agent node 名稱清單。

    Args:
        doc_type: 公文類型
        skip_compliance: 是否跳過合規審查（例如內部簽呈可省略）
        enabled_agents: 若指定，僅啟用此清單中的 Agent

    Returns:
        排序後的 node 名稱清單（按 priority 排序）
    """
    selected: list[str] = []

    for node_name, profile in REVIEW_AGENT_PROFILES.items():
        # 若有白名單，僅啟用白名單中的 Agent
        if enabled_agents is not None and node_name not in enabled_agents:
            continue

        # 跳過合規審查
        if skip_compliance and node_name == "review_compliance":
            continue

        # 檢查是否適用於此公文類型
        applicable = profile.get("applicable_doc_types")
        if applicable is not None and doc_type not in applicable:
            continue

        selected.append(node_name)

    # 按 priority 排序
    selected.sort(key=lambda n: REVIEW_AGENT_PROFILES.get(n, {}).get("priority", 99))

    logger.info(
        "select_review_agents: doc_type=%s, selected=%s",
        doc_type, [REVIEW_AGENT_PROFILES[n]["display_name"] for n in selected],
    )
    return selected
