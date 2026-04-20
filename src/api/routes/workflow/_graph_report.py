"""
workflow package 的 LangGraph QA 報告相容物件。
"""


class _GraphQAReport:
    """輕量 QA 報告物件，模擬原始 QAReport 的 API 介面。"""

    def __init__(
        self,
        overall_score: float,
        risk_summary: str,
        error_count: int,
        warning_count: int,
        agent_results: list,
        rounds_used: int,
        report_markdown: str,
        audit_log: str,
    ):
        self.overall_score = overall_score
        self.risk_summary = risk_summary
        self.error_count = error_count
        self.warning_count = warning_count
        self.agent_results = agent_results
        self.rounds_used = rounds_used
        self.report_markdown = report_markdown
        self.audit_log = audit_log

    def model_dump(self) -> dict:
        """序列化為 dict，與 Pydantic QAReport.model_dump() 相容。"""
        return {
            "overall_score": self.overall_score,
            "risk_summary": self.risk_summary,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "agent_results": self.agent_results,
            "rounds_used": self.rounds_used,
            "report_markdown": self.report_markdown,
            "audit_log": self.audit_log,
        }
