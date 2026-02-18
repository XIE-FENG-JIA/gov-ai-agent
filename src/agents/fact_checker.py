import logging
from rich.console import Console
from src.core.llm import LLMProvider
from src.core.review_models import ReviewResult
from src.core.constants import LLM_TEMPERATURE_PRECISE, MAX_DRAFT_LENGTH
from src.agents.review_parser import parse_review_response

logger = logging.getLogger(__name__)
console = Console()


class FactChecker:
    """
    檢查公文中的事實正確性：法規引用、日期邏輯、數字一致性。
    """

    AGENT_NAME = "Fact Checker"
    CATEGORY = "fact"

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def check(self, draft: str) -> ReviewResult:
        # 防護空值輸入
        if not draft or not draft.strip():
            logger.warning("FactChecker 收到空的草稿")
            return ReviewResult(
                agent_name=self.AGENT_NAME, issues=[], score=0.8
            )

        console.print("[cyan]Agent：事實查核器正在審查...[/cyan]")

        # 截斷過長的草稿
        truncated_draft = draft
        if len(draft) > MAX_DRAFT_LENGTH:
            truncated_draft = draft[:MAX_DRAFT_LENGTH] + "\n...(草稿已截斷，僅檢查前半部分)"

        prompt = f"""You are a Government Regulation Auditor.
Verify the facts in the following draft.

# Checks
1. **Regulation Existence**: If "依據 xxx 法第 x 條" is mentioned, verify if it sounds plausible (AI hallucination check). If unsure, mark as warning.
2. **Date Logic**: Check if dates make sense (e.g., deadline is not in the past).
3. **Numbers**: Check if amounts or quantities are consistent.

# Draft
{truncated_draft}

# Output
JSON format only:
{{
    "issues": [
        {{
            "severity": "error/warning",
            "location": "string",
            "description": "string",
            "suggestion": "string"
        }}
    ],
    "score": 0.0 to 1.0
}}
"""
        response = self.llm.generate(prompt, temperature=LLM_TEMPERATURE_PRECISE)
        return parse_review_response(
            response,
            agent_name=self.AGENT_NAME,
            category=self.CATEGORY,
        )
