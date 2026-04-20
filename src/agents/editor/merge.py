from rich.console import Console
from rich.table import Table

from src.core.constants import CATEGORY_WEIGHTS, assess_risk_level
from src.core.review_models import QAReport, ReviewResult
from src.core.scoring import (
    calculate_risk_scores,
    calculate_weighted_scores,
    get_agent_category,
)

console = Console()


class EditorReportMixin:
    def _generate_qa_report(
        self,
        results: list[ReviewResult],
        timed_out_agents: list[str] | None = None,
    ) -> QAReport:
        """根據所有審查結果產生加權品質報告。"""
        weighted_score, total_weight = self._calculate_weighted_scores(results)
        avg_score = weighted_score / total_weight if total_weight > 0 else 0.0

        weighted_error_score, weighted_warning_score = self._calculate_risk_scores(results)
        risk = "Critical" if total_weight == 0.0 else assess_risk_level(
            weighted_error_score,
            weighted_warning_score,
            avg_score,
        )
        log = self._build_audit_log(
            results,
            avg_score,
            risk,
            weighted_error_score,
            weighted_warning_score,
            timed_out_agents=timed_out_agents,
        )

        return QAReport(
            overall_score=avg_score,
            risk_summary=risk,
            agent_results=results,
            audit_log=log,
        )

    def _calculate_weighted_scores(self, results: list[ReviewResult]) -> tuple[float, float]:
        return calculate_weighted_scores(results)

    def _calculate_risk_scores(self, results: list[ReviewResult]) -> tuple[float, float]:
        return calculate_risk_scores(results)

    @staticmethod
    def _build_audit_log(
        results: list[ReviewResult],
        avg_score: float,
        risk: str,
        weighted_error_score: float,
        weighted_warning_score: float,
        timed_out_agents: list[str] | None = None,
        iteration_history: list[dict] | None = None,
        unfixable_count: int = 0,
    ) -> str:
        parts = [
            "# 品質保證報告\n",
            f"- **加權總分**：{avg_score:.2f}",
            f"- **風險等級**：{risk}",
            f"- **加權錯誤分數**：{weighted_error_score:.1f}",
            f"- **加權警告分數**：{weighted_warning_score:.1f}",
        ]
        if unfixable_count > 0:
            parts.append(f"- **不可自動修復問題**：{unfixable_count} 個")
        parts.append("")

        if iteration_history:
            parts.append("## 迭代審查歷程\n")
            for item in iteration_history:
                phase_info = f", phase={item['phase']}" if "phase" in item else ""
                parts.append(
                    f"- 第 {item['round']} 輪：score={item['score']:.2f}, risk={item['risk']}{phase_info}"
                )
            parts.append("")

        if timed_out_agents:
            parts.append("## 逾時未完成的 Agent\n")
            for name in timed_out_agents:
                parts.append(f"- **{name}**：審查逾時，結果不計入評分")
            parts.append("")

        parts.extend(["## 類別權重\n```"])
        for category, weight in sorted(CATEGORY_WEIGHTS.items(), key=lambda item: -item[1]):
            parts.append(f"{category:15s}: {weight:.1f}x")
        parts.append("```\n\n## 詳細審查結果")

        for result in results:
            parts.append(f"### {result.agent_name}（分數：{result.score:.2f}）")
            if not result.issues:
                parts.append("- 通過")
            for issue in result.issues:
                icon = "[E]" if issue.severity == "error" else "[W]" if issue.severity == "warning" else "[I]"
                parts.append(
                    f"- {icon} **[{issue.risk_level.upper()}]** "
                    f"{issue.location}：{issue.description}"
                )
                if issue.suggestion:
                    parts.append(f"  - *建議*：{issue.suggestion}")
            parts.append("")

        return "\n".join(parts)

    @staticmethod
    def _get_agent_category(agent_name: str) -> str:
        return get_agent_category(agent_name)

    @staticmethod
    def _print_report(report: QAReport):
        risk_style = {
            "Critical": "bold red",
            "High": "red",
            "Moderate": "yellow",
            "Low": "green",
            "Safe": "bold green",
        }.get(report.risk_summary, "white")

        table = Table(
            title=f"品質保證報告（風險：[{risk_style}]{report.risk_summary}[/{risk_style}]）",
            show_lines=True,
            expand=False,
        )
        table.add_column("審查 Agent", style="cyan", no_wrap=True, width=22)
        table.add_column("分數", style="magenta", justify="right", width=7)
        table.add_column("問題", width=60)

        max_desc_length = 70
        for result in report.agent_results:
            issues_list = []
            for issue in result.issues:
                prefix = (
                    "[red]E[/red]"
                    if issue.severity == "error"
                    else "[yellow]W[/yellow]"
                    if issue.severity == "warning"
                    else "[dim]I[/dim]"
                )
                description = issue.description
                if len(description) > max_desc_length:
                    description = description[:max_desc_length] + "..."
                issues_list.append(f"{prefix}: {description}")
            issues_desc = "\n".join(issues_list) if issues_list else "[green]通過[/green]"

            score_style = "red" if result.score < 0.6 else "yellow" if result.score < 0.8 else "green"
            table.add_row(
                result.agent_name,
                f"[{score_style}]{result.score:.2f}[/{score_style}]",
                issues_desc,
            )

        console.print(table)
