"""審查評分工具 — 從 review_parser.py 拆出的格式轉換與評分邏輯。"""
from __future__ import annotations

from src.core.review_models import ReviewIssue, ReviewResult


def format_audit_to_review_result(
    fmt_raw: dict,
    agent_name: str = "Format Auditor",
) -> ReviewResult:
    """
    將 FormatAuditor 的原始字典結果轉換為 ReviewResult。

    這段轉換邏輯原本在 editor.py 和 api_server.py 中各自重複實作，
    現統一由此函式處理。

    Args:
        fmt_raw: FormatAuditor.audit() 的回傳字典，包含 "errors" 和 "warnings"
        agent_name: Agent 名稱

    Returns:
        ReviewResult 物件
    """
    fmt_issues = []
    for err in fmt_raw.get("errors", []):
        if isinstance(err, dict):
            fmt_issues.append(
                ReviewIssue(
                    category="format",
                    severity="error",
                    risk_level="high",
                    location=err.get("location", "文件結構"),
                    description=err.get("description", str(err)),
                    suggestion=err.get("suggestion"),
                )
            )
        else:
            fmt_issues.append(
                ReviewIssue(
                    category="format",
                    severity="error",
                    risk_level="high",
                    location="文件結構",
                    description=str(err),
                )
            )
    for warn in fmt_raw.get("warnings", []):
        if isinstance(warn, dict):
            fmt_issues.append(
                ReviewIssue(
                    category="format",
                    severity="warning",
                    risk_level="medium",
                    location=warn.get("location", "文件結構"),
                    description=warn.get("description", str(warn)),
                    suggestion=warn.get("suggestion"),
                )
            )
        else:
            fmt_issues.append(
                ReviewIssue(
                    category="format",
                    severity="warning",
                    risk_level="medium",
                    location="文件結構",
                    description=str(warn),
                )
            )

    # 依嚴重度動態計算分數，而非硬編碼 0.5
    if not fmt_issues:
        score = 1.0
    else:
        error_count = sum(1 for i in fmt_issues if i.severity == "error")
        warning_count = sum(1 for i in fmt_issues if i.severity == "warning")
        if error_count > 0:
            score = max(0.0, 0.7 - error_count * 0.1)
        else:
            score = max(0.5, 1.0 - warning_count * 0.05)

    return ReviewResult(
        agent_name=agent_name,
        issues=fmt_issues,
        score=score,
        confidence=1.0,
    )
