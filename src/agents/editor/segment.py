import logging

from rich.console import Console

from src.core.review_models import QAReport

logger = logging.getLogger(__name__)
console = Console()


class EditorSegmentMixin:
    def _review_single(self, draft: str, doc_type: str) -> tuple[str, QAReport]:
        """對單一草稿（或分段）執行單次並行審查。"""
        results, timed_out = self._execute_review(draft, doc_type)
        report = self._generate_qa_report(results, timed_out)
        logger.info(
            "審查完成：score=%.2f, risk=%s, agents=%d, timed_out=%d",
            report.overall_score,
            report.risk_summary,
            len(results),
            len(timed_out),
        )
        self._print_report(report)

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

    def _segmented_review(self, draft: str, doc_type: str) -> tuple[str, QAReport]:
        """對超長草稿分段審查，合併各段結果為完整 QA 報告。"""
        segments = self._split_draft(draft)
        logger.info("超長草稿（%d 字）分為 %d 段審查", len(draft), len(segments))
        console.print(
            f"[yellow]草稿超過 {self._SEGMENT_THRESHOLD} 字，分為 {len(segments)} 段審查[/yellow]"
        )

        all_results = []
        all_timed_out: list[str] = []
        for idx, segment in enumerate(segments):
            console.print(f"\n[cyan]--- 審查第 {idx + 1}/{len(segments)} 段（{len(segment)} 字）---[/cyan]")
            seg_results, seg_timed_out = self._execute_review(segment, doc_type)
            all_timed_out.extend(seg_timed_out)
            for result in seg_results:
                if len(segments) > 1:
                    result.agent_name = f"{result.agent_name}（段{idx + 1}）"
                all_results.append(result)

        report = self._generate_qa_report(all_results, all_timed_out)
        logger.info(
            "分段審查完成：segments=%d, score=%.2f, risk=%s",
            len(segments),
            report.overall_score,
            report.risk_summary,
        )
        self._print_report(report)

        if report.risk_summary in ["Critical", "High", "Moderate"]:
            console.print(
                f"\n[bold yellow]風險等級：{report.risk_summary}。"
                f"草稿長度（{len(draft)} 字）超過自動修正上限，"
                "請依據上方審查建議手動修正。[/bold yellow]"
            )
        else:
            console.print(
                f"\n[bold green]品質分數（{report.overall_score:.2f}）優良，"
                "無需修改。[/bold green]"
            )
        return draft, report

    @staticmethod
    def _split_draft(draft: str) -> list[str]:
        """將超長草稿分段。優先在換行處分割以保持段落完整性。"""
        from src.agents.editor import EditorInChief

        segment_size = EditorInChief._SEGMENT_SIZE
        if len(draft) <= segment_size:
            return [draft]

        segments: list[str] = []
        start = 0
        while start < len(draft):
            end = min(start + segment_size, len(draft))
            if end < len(draft):
                newline_pos = draft.rfind("\n", start + segment_size // 2, end)
                if newline_pos > start:
                    end = newline_pos + 1
            segments.append(draft[start:end])
            start = end
        return segments
