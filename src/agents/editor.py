from typing import List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from rich.table import Table
from src.core.llm import LLMProvider
from src.core.review_models import ReviewResult, QAReport
from src.core.constants import (
    CATEGORY_WEIGHTS,
    WARNING_WEIGHT_FACTOR,
    EDITOR_MAX_WORKERS,
    DEFAULT_FAILED_SCORE,
    DEFAULT_FAILED_CONFIDENCE,
    MAX_DRAFT_LENGTH,
    MAX_FEEDBACK_LENGTH,
    assess_risk_level,
)
from src.agents.auditor import FormatAuditor
from src.agents.style_checker import StyleChecker
from src.agents.fact_checker import FactChecker
from src.agents.consistency_checker import ConsistencyChecker
from src.agents.compliance_checker import ComplianceChecker
from src.agents.review_parser import format_audit_to_review_result
from src.knowledge.manager import KnowledgeBaseManager

console = Console()


class EditorInChief:
    """
    協調所有審查 Agent 並產生最終修正版草稿。
    支援並行執行以加速審查。
    """

    def __init__(self, llm: LLMProvider, kb_manager: Optional[KnowledgeBaseManager] = None):
        self.llm = llm
        self.kb_manager = kb_manager
        self.format_auditor = FormatAuditor(llm, kb_manager)
        self.style_checker = StyleChecker(llm)
        self.fact_checker = FactChecker(llm)
        self.consistency_checker = ConsistencyChecker(llm)
        self.compliance_checker = ComplianceChecker(llm, kb_manager)

    def review_and_refine(self, draft: str, doc_type: str) -> Tuple[str, QAReport]:
        """
        並行執行所有審查 Agent，彙整結果，必要時自動修正草稿。
        """
        console.rule("[bold red]多 Agent 審查會議（並行模式）[/bold red]")

        # 1. 先同步執行格式審查（規則導向，速度快）
        fmt_raw = self.format_auditor.audit(draft, doc_type)
        format_result = format_audit_to_review_result(fmt_raw)

        # 2. 其餘 Agent 並行執行
        results = [format_result]
        parallel_tasks = {
            "Style Checker": lambda: self.style_checker.check(draft),
            "Fact Checker": lambda: self.fact_checker.check(draft),
            "Consistency Checker": lambda: self.consistency_checker.check(draft),
            "Compliance Checker": lambda: self.compliance_checker.check(draft),
        }

        console.print(
            f"[cyan]啟動並行審查 ({len(parallel_tasks)} Agents 同時執行)...[/cyan]"
        )

        with ThreadPoolExecutor(max_workers=EDITOR_MAX_WORKERS) as executor:
            future_to_agent = {
                executor.submit(task): name
                for name, task in parallel_tasks.items()
            }

            for future in as_completed(future_to_agent):
                agent_name = future_to_agent[future]
                try:
                    result = future.result()
                    results.append(result)
                    console.print(f"[green]v {agent_name} 完成[/green]")
                except Exception as exc:
                    console.print(f"[red]x {agent_name} 失敗: {str(exc)[:50]}[/red]")
                    results.append(ReviewResult(
                        agent_name=agent_name,
                        issues=[],
                        score=DEFAULT_FAILED_SCORE,
                        confidence=DEFAULT_FAILED_CONFIDENCE,
                    ))

        # 3. 產生 QA 報告
        report = self._generate_qa_report(results)
        self._print_report(report)

        # 4. 判定是否需要自動修正
        if report.risk_summary in ["Critical", "High", "Moderate"]:
            console.print(
                f"\n[bold yellow]風險等級：{report.risk_summary}。"
                "正在啟動自動修正...[/bold yellow]"
            )
            refined_draft = self._auto_refine(draft, results)
            return refined_draft, report

        console.print(
            f"\n[bold green]品質分數（{report.overall_score:.2f}）優良，"
            "無需修改。[/bold green]"
        )
        return draft, report

    # ------------------------------------------------------------------
    # 內部輔助方法
    # ------------------------------------------------------------------

    def _generate_qa_report(self, results: List[ReviewResult]) -> QAReport:
        """根據所有審查結果產生加權品質報告。"""
        weighted_score, total_weight = self._calculate_weighted_scores(results)
        avg_score = weighted_score / total_weight if total_weight > 0 else 0.0

        weighted_error_score, weighted_warning_score = self._calculate_risk_scores(results)

        risk = assess_risk_level(weighted_error_score, weighted_warning_score, avg_score)
        log = self._build_audit_log(
            results, avg_score, risk,
            weighted_error_score, weighted_warning_score,
        )

        return QAReport(
            overall_score=avg_score,
            risk_summary=risk,
            agent_results=results,
            audit_log=log,
        )

    def _calculate_weighted_scores(
        self, results: List[ReviewResult]
    ) -> Tuple[float, float]:
        """計算加權品質分數。"""
        weighted_score = 0.0
        total_weight = 0.0

        for res in results:
            agent_category = self._get_agent_category(res.agent_name)
            weight = CATEGORY_WEIGHTS.get(agent_category, 1.0)
            weighted_score += res.score * weight * res.confidence
            total_weight += weight * res.confidence

        return weighted_score, total_weight

    def _calculate_risk_scores(
        self, results: List[ReviewResult]
    ) -> Tuple[float, float]:
        """計算加權風險分數（錯誤和警告）。"""
        weighted_error_score = 0.0
        weighted_warning_score = 0.0

        for res in results:
            agent_category = self._get_agent_category(res.agent_name)
            weight = CATEGORY_WEIGHTS.get(agent_category, 1.0)

            for issue in res.issues:
                if issue.severity == "error":
                    weighted_error_score += weight
                elif issue.severity == "warning":
                    weighted_warning_score += weight * WARNING_WEIGHT_FACTOR

        return weighted_error_score, weighted_warning_score

    @staticmethod
    def _build_audit_log(
        results: List[ReviewResult],
        avg_score: float,
        risk: str,
        weighted_error_score: float,
        weighted_warning_score: float,
    ) -> str:
        """建構 Markdown 格式的審計日誌。"""
        log = "# 品質保證報告\n\n"
        log += f"- **加權總分**：{avg_score:.2f}\n"
        log += f"- **風險等級**：{risk}\n"
        log += f"- **加權錯誤分數**：{weighted_error_score:.1f}\n"
        log += f"- **加權警告分數**：{weighted_warning_score:.1f}\n\n"
        log += "## 類別權重\n```\n"
        for cat, weight in sorted(CATEGORY_WEIGHTS.items(), key=lambda x: -x[1]):
            log += f"{cat:15s}: {weight:.1f}x\n"
        log += "```\n\n## 詳細審查結果\n"

        for res in results:
            log += f"### {res.agent_name}（分數：{res.score:.2f}）\n"
            if not res.issues:
                log += "- 通過\n"
            for issue in res.issues:
                icon = (
                    "[E]" if issue.severity == "error"
                    else "[W]" if issue.severity == "warning"
                    else "[I]"
                )
                log += (
                    f"- {icon} **[{issue.risk_level.upper()}]** "
                    f"{issue.location}：{issue.description}\n"
                )
                if issue.suggestion:
                    log += f"  - *建議*：{issue.suggestion}\n"
            log += "\n"

        return log

    @staticmethod
    def _get_agent_category(agent_name: str) -> str:
        """推斷 Agent 所屬的類別以取得對應權重。"""
        name_lower = agent_name.lower()
        if "format" in name_lower or "auditor" in name_lower:
            return "format"
        elif "compliance" in name_lower or "policy" in name_lower:
            return "compliance"
        elif "fact" in name_lower:
            return "fact"
        elif "consistency" in name_lower:
            return "consistency"
        return "style"  # 預設為最低權重

    def _auto_refine(self, draft: str, results: List[ReviewResult]) -> str:
        """根據審查結果自動修正草稿。"""
        feedback_str = ""
        for res in results:
            for issue in res.issues:
                # 安全處理 suggestion 可能為 None 的情況
                suggestion_text = issue.suggestion or "請自行判斷修正方式"
                feedback_str += (
                    f"- [{res.agent_name}] {issue.severity.upper()}: "
                    f"{issue.description} (Fix: {suggestion_text})\n"
                )

        if not feedback_str:
            return draft

        # 截斷過長的回饋和草稿，避免超出 LLM 上下文限制
        if len(feedback_str) > MAX_FEEDBACK_LENGTH:
            feedback_str = feedback_str[:MAX_FEEDBACK_LENGTH] + "\n...(回饋已截斷)"

        truncated_draft = draft
        if len(draft) > MAX_DRAFT_LENGTH:
            truncated_draft = draft[:MAX_DRAFT_LENGTH] + "\n...(草稿已截斷)"

        prompt = f"""You are the Editor-in-Chief.
Refine the following government document draft based on the feedback from review agents.

# Draft
{truncated_draft}

# Feedback to Address
{feedback_str}

# Instruction
Rewrite the draft to fix these issues while maintaining the standard format.
Return ONLY the new draft markdown.
"""
        console.print("[cyan]Editor 正在重新撰寫...[/cyan]")
        result = self.llm.generate(prompt)

        # 若 LLM 回傳空值，保留原始草稿
        if not result or not result.strip() or result.startswith("Error"):
            console.print("[yellow]Editor 修正失敗，保留原始草稿[/yellow]")
            return draft

        return result

    @staticmethod
    def _print_report(report: QAReport):
        """在終端機輸出 QA 報告表格。"""
        table = Table(
            title=f"品質保證報告（風險：{report.risk_summary}）",
            show_lines=True,
            expand=False,
        )
        table.add_column("審查 Agent", style="cyan", no_wrap=True, width=22)
        table.add_column("分數", style="magenta", justify="right", width=7)
        table.add_column("問題", style="red", width=60)

        max_desc_length = 75
        for res in report.agent_results:
            issues_list = []
            for issue in res.issues:
                prefix = (
                    "E" if issue.severity == "error"
                    else "W" if issue.severity == "warning"
                    else "I"
                )
                desc = issue.description
                if len(desc) > max_desc_length:
                    desc = desc[:max_desc_length] + "..."
                issues_list.append(f"{prefix}: {desc}")
            issues_desc = "\n".join(issues_list) if issues_list else "通過"
            table.add_row(res.agent_name, f"{res.score:.2f}", issues_desc)

        console.print(table)
