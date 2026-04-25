import logging

from rich.console import Console

from src.agents.review_parser import format_audit_to_review_result
from src.core.constants import (
    CONVERGENCE_SAFETY_LIMIT,
    CONVERGENCE_STALE_ROUNDS,
    DEFAULT_FAILED_CONFIDENCE,
    DEFAULT_FAILED_SCORE,
)
from src.core.review_models import QAReport, IterationState, ReviewResult

logger = logging.getLogger(__name__)
console = Console()


class EditorFlowMixin:
    def _iterative_review(
        self, draft: str, doc_type: str, max_rounds: int, *, show_rounds: bool = False
    ) -> tuple[str, QAReport]:
        """迭代審查：review → refine → re-review，直到收斂或達上限。"""
        current_draft = draft
        best_draft = draft
        prev_draft: str | None = None
        iteration_history: list[dict] = []
        final_report: QAReport | None = None
        best_report: QAReport | None = None
        best_score = -1.0

        for round_num in range(1, max_rounds + 1):
            console.print(f"\n[bold cyan]--- 審查第 {round_num}/{max_rounds} 輪 ---[/bold cyan]")
            results, timed_out = self._execute_review(current_draft, doc_type)
            report = self._generate_qa_report(results, timed_out)
            logger.info(
                "第 %d 輪審查完成：score=%.2f, risk=%s, agents=%d, timed_out=%d",
                round_num,
                report.overall_score,
                report.risk_summary,
                len(results),
                len(timed_out),
            )
            self._print_report(report)
            iteration_history.append(
                {"round": round_num, "score": report.overall_score, "risk": report.risk_summary}
            )

            if report.overall_score >= best_score:
                best_score = report.overall_score
                best_report = report
                best_draft = current_draft

            if report.risk_summary in ["Safe", "Low"]:
                console.print(
                    f"\n[bold green]第 {round_num} 輪品質達標"
                    f"（{report.risk_summary}），停止迭代。[/bold green]"
                )
                final_report = report
                break

            all_failed = all(r.confidence == 0.0 for r in results) if results else False
            if report.risk_summary == "Critical" and all_failed:
                logger.warning("所有審查 Agent 失敗，中止迭代")
                console.print("[red]所有審查 Agent 失敗，中止迭代。[/red]")
                final_report = report
                break

            if len(iteration_history) >= 2:
                prev_score = iteration_history[-2]["score"]
                if report.overall_score <= prev_score:
                    console.print(
                        f"\n[yellow]分數未改善"
                        f"（{prev_score:.2f} → {report.overall_score:.2f}），"
                        "停止迭代。[/yellow]"
                    )
                    final_report = best_report or report
                    current_draft = best_draft
                    break

            if round_num < max_rounds and report.risk_summary in ["Critical", "High", "Moderate"]:
                console.print(
                    f"\n[bold yellow]風險等級：{report.risk_summary}。"
                    "正在啟動自動修正...[/bold yellow]"
                )
                prev_draft = current_draft
                current_draft = self._auto_refine(current_draft, results)
                if show_rounds and current_draft != prev_draft:
                    self._print_round_draft(
                        round_num,
                        "iterative",
                        current_draft,
                        prev_draft,
                        report.overall_score,
                        report.risk_summary,
                    )
            else:
                final_report = best_report or report
                current_draft = best_draft
                break

            final_report = best_report or report

        if final_report is None:
            final_report = best_report

        final_report.rounds_used = len(iteration_history)
        final_report.iteration_history = iteration_history
        if len(iteration_history) > 1:
            weighted_score, total_weight = self._calculate_weighted_scores(final_report.agent_results)
            avg_score = weighted_score / total_weight if total_weight > 0 else 0.0
            w_err, w_warn = self._calculate_risk_scores(final_report.agent_results)
            final_report.audit_log = self._build_audit_log(
                final_report.agent_results,
                avg_score,
                final_report.risk_summary,
                w_err,
                w_warn,
                iteration_history=iteration_history,
            )
        return current_draft, final_report

    def _convergence_review(
        self, draft: str, doc_type: str, phases: tuple[str, ...], *, show_rounds: bool = False
    ) -> tuple[str, QAReport]:
        """分層收斂迭代：按 error → warning → info 逐層消除問題。"""
        state = IterationState(draft, phases)
        current_draft = draft
        prev_draft: str | None = None
        final_report: QAReport | None = None

        while state.round_number < CONVERGENCE_SAFETY_LIMIT:
            phase = state.current_phase
            is_first_phase_round = state.phase_round == 0
            console.print(
                f"\n[bold cyan]--- 第 {state.round_number + 1} 輪"
                f"（Phase: {phase.upper()}, Phase 內第 {state.phase_round + 1} 輪）---[/bold cyan]"
            )

            if is_first_phase_round:
                results, timed_out = self._execute_review(current_draft, doc_type)
            else:
                previous_results = final_report.agent_results if final_report else []
                results, timed_out = self._execute_targeted_review(
                    current_draft, doc_type, previous_results, phase
                )

            report = self._generate_qa_report(results, timed_out)
            state.record_round(report.overall_score, report.risk_summary)
            self._print_report(report)
            logger.info(
                "第 %d 輪（Phase=%s）：score=%.2f, risk=%s",
                state.round_number,
                phase,
                report.overall_score,
                report.risk_summary,
            )

            fixable = state.issue_tracker.get_fixable_issues(results, phase)
            if not fixable:
                console.print(
                    f"\n[bold green]Phase {phase.upper()} 完成"
                    f"（無剩餘 {phase} 問題）[/bold green]"
                )
                if not state.advance_phase():
                    console.print("[bold green]所有 Phase 完成，品質已達標！[/bold green]")
                    final_report = report
                    break
                final_report = report
                continue

            if state.is_stale:
                console.print(
                    f"\n[yellow]Phase {phase.upper()} 連續"
                    f" {CONVERGENCE_STALE_ROUNDS} 輪無改善，"
                    f"跳至下一 Phase（{len(fixable)} 個問題未解決）[/yellow]"
                )
                if not state.advance_phase():
                    final_report = report
                    break
                final_report = report
                continue

            all_failed = all(r.confidence == 0.0 for r in results) if results else False
            if all_failed:
                logger.warning("所有審查 Agent 失敗，中止迭代")
                console.print("[red]所有審查 Agent 失敗，中止迭代。[/red]")
                final_report = report
                break

            console.print(f"\n[bold yellow]修正 {len(fixable)} 個 {phase} 問題...[/bold yellow]")
            for agent_name, issue in fixable:
                state.issue_tracker.record_attempt(agent_name, issue)

            prev_draft = current_draft
            refined = self._layered_refine(current_draft, fixable)
            verify_results, _ = self._execute_targeted_review(refined, doc_type, results, phase)
            verify_report = self._generate_qa_report(verify_results, [])

            if verify_report.overall_score < state.best_score * 0.95:
                console.print("[yellow]修正導致品質下降，嘗試替代策略...[/yellow]")
                refined = self._layered_refine(state.best_draft, fixable, alternative=True)
                verify_results2, _ = self._execute_targeted_review(refined, doc_type, results, phase)
                verify_report2 = self._generate_qa_report(verify_results2, [])

                if verify_report2.overall_score < state.best_score * 0.95:
                    console.print("[yellow]替代策略也失敗，回滾到最佳版本[/yellow]")
                    current_draft = state.best_draft
                    final_report = report
                    continue

                current_draft = refined
                state.update_best_draft(refined, verify_report2.overall_score)
                final_report = self._generate_qa_report(verify_results2, [])
                if show_rounds:
                    self._print_round_draft(
                        state.round_number,
                        phase,
                        current_draft,
                        prev_draft,
                        final_report.overall_score,
                        final_report.risk_summary,
                    )
                continue

            current_draft = refined
            state.update_best_draft(refined, verify_report.overall_score)
            final_report = self._generate_qa_report(verify_results, [])
            if show_rounds:
                self._print_round_draft(
                    state.round_number,
                    phase,
                    current_draft,
                    prev_draft,
                    final_report.overall_score,
                    final_report.risk_summary,
                )

        if final_report is None:
            final_report = self._generate_qa_report([], [])

        final_report.rounds_used = state.round_number
        final_report.iteration_history = state.history
        if state.history:
            weighted_score, total_weight = self._calculate_weighted_scores(final_report.agent_results)
            avg_score = weighted_score / total_weight if total_weight > 0 else 0.0
            w_err, w_warn = self._calculate_risk_scores(final_report.agent_results)
            final_report.audit_log = self._build_audit_log(
                final_report.agent_results,
                avg_score,
                final_report.risk_summary,
                w_err,
                w_warn,
                iteration_history=state.history,
                unfixable_count=state.issue_tracker.unfixable_count,
            )
        return current_draft, final_report

    def _execute_targeted_review(
        self,
        draft: str,
        doc_type: str,
        prev_results: list[ReviewResult],
        phase: str,
    ) -> tuple[list[ReviewResult], list[str]]:
        """只重跑上一輪在指定 phase 有 issues 的 Agent，其餘沿用舊結果。"""
        affected_agents = {
            result.agent_name
            for result in prev_results
            if any(issue.severity == phase for issue in result.issues)
        }
        if not affected_agents:
            return prev_results, []

        targeted_tasks = {
            "Format Auditor": lambda: format_audit_to_review_result(
                self.format_auditor.audit(draft, doc_type)
            ),
            "Citation Checker": lambda: self.citation_checker.check(draft),
            "Style Checker": lambda: self.style_checker.check(draft),
            "Fact Checker": lambda: self.fact_checker.check(draft, doc_type=doc_type),
            "Consistency Checker": lambda: self.consistency_checker.check(draft),
            "Compliance Checker": lambda: self.compliance_checker.check(draft),
        }
        rerun_agents = {name: targeted_tasks[name] for name in affected_agents if name in targeted_tasks}
        preserved = [result for result in prev_results if result.agent_name not in rerun_agents]
        if not rerun_agents:
            return prev_results, []

        results: list[ReviewResult] = []
        future_to_agent = {self._executor.submit(task): name for name, task in rerun_agents.items()}
        for future, agent_name in future_to_agent.items():
            try:
                results.append(future.result())
            except (RuntimeError, OSError, ValueError) as exc:
                results.append(
                    ReviewResult(
                        agent_name=agent_name,
                        issues=[],
                        score=DEFAULT_FAILED_SCORE,
                        confidence=DEFAULT_FAILED_CONFIDENCE,
                    )
                )
        results.extend(preserved)
        return results, []
