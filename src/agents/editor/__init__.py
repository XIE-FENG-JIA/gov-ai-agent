import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.console import Console

from src.agents.auditor import FormatAuditor
from src.agents.citation_checker import CitationChecker
from src.agents.compliance_checker import ComplianceChecker
from src.agents.consistency_checker import ConsistencyChecker
from src.agents.fact_checker import FactChecker
from src.agents.review_parser import format_audit_to_review_result
from src.agents.style_checker import StyleChecker
from src.agents.editor.flow import EditorFlowMixin
from src.agents.editor.merge import EditorReportMixin
from src.agents.editor.refine import EditorRefineMixin
from src.agents.editor.segment import EditorSegmentMixin
from src.core.constants import (
    DEFAULT_FAILED_CONFIDENCE,
    DEFAULT_FAILED_SCORE,
    DEFAULT_MAX_REVIEW_ROUNDS,
    EDITOR_MAX_WORKERS,
    PARALLEL_REVIEW_TIMEOUT,
)
from src.core.llm import LLMProvider
from src.core.review_models import QAReport, ReviewResult
from src.knowledge.manager import KnowledgeBaseManager

logger = logging.getLogger(__name__)
console = Console()


class EditorInChief(EditorFlowMixin, EditorRefineMixin, EditorSegmentMixin, EditorReportMixin):
    """
    協調所有審查 Agent 並產生最終修正版草稿。
    支援並行執行以加速審查。
    """

    # 超長草稿分段審查的字元門檻
    _SEGMENT_THRESHOLD = 15000
    # 每段最大字元數
    _SEGMENT_SIZE = 12000

    def __init__(self, llm: LLMProvider, kb_manager: KnowledgeBaseManager | None = None) -> None:
        self.llm = llm
        self.kb_manager = kb_manager

        # 初始化即時查詢服務（失敗時設為 None，降級為純 LLM）
        law_verifier = None
        policy_fetcher = None
        try:
            from src.knowledge.realtime_lookup import LawVerifier, RecentPolicyFetcher

            law_verifier = LawVerifier()
            policy_fetcher = RecentPolicyFetcher()
        except Exception as exc:
            logger.warning("即時查詢服務初始化失敗: %s", exc)

        self.format_auditor = FormatAuditor(llm, kb_manager)
        self.citation_checker = CitationChecker()
        self.style_checker = StyleChecker(llm)
        self.fact_checker = FactChecker(llm, law_verifier=law_verifier)
        self.consistency_checker = ConsistencyChecker(llm)
        self.compliance_checker = ComplianceChecker(
            llm, kb_manager, policy_fetcher=policy_fetcher
        )

        # 共用執行緒池：避免每輪審查都建/銷毀 ThreadPoolExecutor
        self._executor = ThreadPoolExecutor(max_workers=EDITOR_MAX_WORKERS)

    def close(self) -> None:
        """關閉共用執行緒池，釋放 worker threads。"""
        self._executor.shutdown(wait=False)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def __del__(self) -> None:
        # 安全網：GC 回收時確保 executor 被關閉
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            pass

    def run_review_only(self, draft: str, doc_type: str) -> QAReport:
        """執行一次完整多 Agent 審查，不進行任何草稿修正。"""
        console.rule("[bold cyan]多 Agent 審查（單輪，不修正）[/bold cyan]")
        results, timed_out = self._execute_review(draft, doc_type)
        report = self._generate_qa_report(results, timed_out)
        self._print_report(report)
        return report

    def review_and_refine(
        self,
        draft: str,
        doc_type: str,
        max_rounds: int = DEFAULT_MAX_REVIEW_ROUNDS,
        *,
        convergence: bool = False,
        skip_info: bool = False,
        show_rounds: bool = False,
    ) -> tuple[str, QAReport]:
        """
        並行執行所有審查 Agent，彙整結果，必要時迭代修正草稿。

        超過 15000 字的草稿會分段送審（不迭代），最後合併各段結果。
        逾時時保留已完成 Agent 的結果，並在報告中標註未完成項。
        """
        mode_label = "分層收斂" if convergence else "經典"
        logger.info(
            "開始多 Agent 審查（mode=%s, doc_type=%s, draft_len=%d, max_rounds=%s）",
            mode_label,
            doc_type,
            len(draft),
            "unlimited" if convergence else max_rounds,
        )
        console.rule(f"[bold red]多 Agent 審查會議（{mode_label}模式）[/bold red]")

        if len(draft) > self._SEGMENT_THRESHOLD:
            if convergence:
                logger.warning(
                    "草稿長度 %d 超過分段門檻 %d，convergence 模式將降級為分段審查",
                    len(draft),
                    self._SEGMENT_THRESHOLD,
                )
                console.print(
                    f"[yellow]草稿超過 {self._SEGMENT_THRESHOLD} 字，"
                    "分層收斂模式將降級為分段審查。[/yellow]"
                )
            return self._segmented_review(draft, doc_type)

        if convergence:
            phases = ("error", "warning") if skip_info else self._convergence_phases
            return self._convergence_review(draft, doc_type, phases, show_rounds=show_rounds)

        return self._iterative_review(draft, doc_type, max_rounds, show_rounds=show_rounds)

    @property
    def _convergence_phases(self) -> tuple[str, ...]:
        from src.core.constants import CONVERGENCE_PHASES

        return CONVERGENCE_PHASES

    def _execute_review(
        self,
        draft: str,
        doc_type: str,
    ) -> tuple[list[ReviewResult], list[str]]:
        """執行一輪並行審查，回傳 (results, timed_out_agents)。"""
        fmt_raw = self.format_auditor.audit(draft, doc_type)
        format_result = format_audit_to_review_result(fmt_raw)

        results = [format_result]
        timed_out_agents: list[str] = []
        parallel_tasks = {
            "Citation Checker": lambda: self.citation_checker.check(draft),
            "Style Checker": lambda: self.style_checker.check(draft),
            "Fact Checker": lambda: self.fact_checker.check(draft, doc_type=doc_type),
            "Consistency Checker": lambda: self.consistency_checker.check(draft),
            "Compliance Checker": lambda: self.compliance_checker.check(draft),
        }

        console.print(
            f"[cyan]啟動並行審查 ({len(parallel_tasks)} Agents 同時執行)...[/cyan]"
        )

        future_to_agent = {
            self._executor.submit(task): name for name, task in parallel_tasks.items()
        }

        try:
            for future in as_completed(future_to_agent, timeout=PARALLEL_REVIEW_TIMEOUT):
                agent_name = future_to_agent[future]
                try:
                    result = future.result()
                    results.append(result)
                    console.print(f"[green]v {agent_name} 完成[/green]")
                except Exception as exc:
                    logger.error("審查 Agent '%s' 執行失敗: %s", agent_name, exc)
                    console.print(f"[red]x {agent_name} 失敗: {str(exc)[:50]}[/red]")
                    results.append(
                        ReviewResult(
                            agent_name=agent_name,
                            issues=[],
                            score=DEFAULT_FAILED_SCORE,
                            confidence=DEFAULT_FAILED_CONFIDENCE,
                        )
                    )
        except TimeoutError:
            logger.error("並行審查逾時（%ds），保留已完成結果", PARALLEL_REVIEW_TIMEOUT)
            console.print("[red]並行審查逾時，將以已完成的結果繼續。[/red]")
            for future, name in future_to_agent.items():
                if future.done():
                    continue
                cancelled = future.cancel()
                logger.warning(
                    "逾時取消 Agent '%s': %s",
                    name,
                    "已取消" if cancelled else "取消失敗（任務正在執行）",
                )
                timed_out_agents.append(name)
                results.append(
                    ReviewResult(
                        agent_name=name,
                        issues=[],
                        score=DEFAULT_FAILED_SCORE,
                        confidence=DEFAULT_FAILED_CONFIDENCE,
                    )
                )

        return results, timed_out_agents


Editor = EditorInChief

__all__ = ["Editor", "EditorInChief"]
