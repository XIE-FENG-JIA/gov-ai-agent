from __future__ import annotations

import logging

from src.agents.validators import validator_registry
from src.core.constants import DEFAULT_REVIEW_SCORE
from src.core.review_models import ReviewIssue, ReviewResult
from src.document import REFERENCE_SECTION_HEADING
from src.document.citation_metadata import extract_reference_entries

logger = logging.getLogger(__name__)


def _normalize_severity(description: str) -> str:
    if any(token in description for token in ("待補依據", "缺少", "孤兒引用", "無法解析", "不可追溯")):
        return "error"
    return "warning"


class CitationChecker:
    """Repo-owned citation traceability checker."""

    AGENT_NAME = "Citation Checker"
    CATEGORY = "fact"

    def check(self, draft: str) -> ReviewResult:
        if not draft or not draft.strip():
            logger.warning("CitationChecker 收到空的草稿")
            return ReviewResult(
                agent_name=self.AGENT_NAME,
                issues=[],
                score=DEFAULT_REVIEW_SCORE,
            )

        raw_issues = []
        raw_issues.extend(validator_registry.check_citation_level(draft))
        raw_issues.extend(validator_registry.check_evidence_presence(draft))
        raw_issues.extend(validator_registry.check_citation_integrity(draft))
        raw_issues.extend(self._check_reference_traceability(draft))

        issues = [
            ReviewIssue(
                category=self.CATEGORY,
                severity=_normalize_severity(str(item.get("description", ""))),
                risk_level="high" if _normalize_severity(str(item.get("description", ""))) == "error" else "medium",
                location=str(item.get("location", "引用追溯")),
                description=str(item.get("description", "")),
                suggestion=(None if item.get("suggestion") is None else str(item.get("suggestion"))),
            )
            for item in raw_issues
            if item.get("description")
        ]

        error_count = sum(1 for issue in issues if issue.severity == "error")
        warning_count = sum(1 for issue in issues if issue.severity == "warning")
        score = max(0.0, min(1.0, 1.0 - error_count * 0.2 - warning_count * 0.05))
        confidence = 1.0 if issues else 0.95
        return ReviewResult(
            agent_name=self.AGENT_NAME,
            issues=issues,
            score=score,
            confidence=confidence,
        )

    @staticmethod
    def _check_reference_traceability(draft: str) -> list[dict]:
        inline_citations_present = "[^" in draft
        has_reference_heading = REFERENCE_SECTION_HEADING in draft or "### 參考來源" in draft
        reference_entries = extract_reference_entries(draft)

        issues: list[dict] = []
        if has_reference_heading and inline_citations_present and not reference_entries:
            issues.append(
                {
                    "description": "引用段落存在，但參考來源定義無法解析為 repo 標準格式。",
                    "location": "參考來源段落",
                    "suggestion": "將每條來源改為 `[^n]: [Level A/B] 標題 | URL: ... | Hash: ...` 格式。",
                }
            )
            return issues

        for entry in reference_entries:
            if entry["source_url"] or entry["content_hash"]:
                continue
            issues.append(
                {
                    "description": f"引用 [^{entry['index']}] 不可追溯：缺少 URL 或內容雜湊。",
                    "location": f"引用 [^{entry['index']}]",
                    "suggestion": (
                        f"為 [^{entry['index']}] 補上 `| URL: ...` 或 `| Hash: ...`，"
                        "確保可回查原始依據。"
                    ),
                }
            )
        return issues
