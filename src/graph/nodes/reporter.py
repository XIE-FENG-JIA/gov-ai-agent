"""
build_report node — 產生 Markdown 品質報告
"""

import logging
from typing import Any

from src.graph.state import GovDocState

logger = logging.getLogger(__name__)


def build_report(state: GovDocState) -> dict:
    """根據彙整報告產生人類可讀的 Markdown 品質報告。

    讀取: aggregated_report, refinement_round
    寫入: report, phase
    """
    try:
        report_data: dict[str, Any] = state.get("aggregated_report", {})
        refinement_round = state.get("refinement_round", 0)

        overall_score = report_data.get("overall_score", 0.0)
        risk_summary = report_data.get("risk_summary", "Unknown")
        error_count = report_data.get("error_count", 0)
        warning_count = report_data.get("warning_count", 0)
        agent_results = report_data.get("agent_results", [])

        parts: list[str] = [
            "# 品質保證報告\n",
            f"- **加權總分**: {overall_score:.2f}",
            f"- **風險等級**: {risk_summary}",
            f"- **錯誤數量**: {error_count}",
            f"- **警告數量**: {warning_count}",
            f"- **精煉輪次**: {refinement_round}",
            "",
        ]

        # 各 Agent 詳細結果
        parts.append("## 詳細審查結果\n")
        for res in agent_results:
            agent_name = res.get("agent_name", "Unknown")
            score = res.get("score", 0.0)
            issues = res.get("issues", [])

            parts.append(f"### {agent_name}（分數: {score:.2f}）")
            if not issues:
                parts.append("- 通過")
            else:
                for issue in issues:
                    severity = issue.get("severity", "info")
                    icon = {"error": "[E]", "warning": "[W]"}.get(severity, "[I]")
                    location = issue.get("location", "")
                    description = issue.get("description", "")
                    suggestion = issue.get("suggestion", "")
                    parts.append(f"- {icon} {location}: {description}")
                    if suggestion:
                        parts.append(f"  - *建議*: {suggestion}")
            parts.append("")

        report_md = "\n".join(parts)

        return {
            "report": report_md,
            "phase": "report_built",
        }

    except (ValueError, TypeError, AttributeError, KeyError) as exc:
        logger.exception("build_report 失敗: %s", exc)
        return {
            "report": f"# 品質報告產生失敗\n\n錯誤: {exc}",
            "phase": "report_built",
        }
