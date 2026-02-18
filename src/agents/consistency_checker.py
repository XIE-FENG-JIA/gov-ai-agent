import logging
from rich.console import Console
from src.core.llm import LLMProvider
from src.core.review_models import ReviewResult
from src.core.constants import LLM_TEMPERATURE_PRECISE, MAX_DRAFT_LENGTH
from src.agents.review_parser import parse_review_response

logger = logging.getLogger(__name__)
console = Console()


class ConsistencyChecker:
    """
    檢查公文各段落間的邏輯一致性：主旨與內容、說明與辦法之間的關聯。
    """

    AGENT_NAME = "Consistency Checker"
    CATEGORY = "consistency"

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def check(self, draft: str) -> ReviewResult:
        # 防護空值輸入
        if not draft or not draft.strip():
            logger.warning("ConsistencyChecker 收到空的草稿")
            return ReviewResult(
                agent_name=self.AGENT_NAME, issues=[], score=0.8
            )

        console.print("[cyan]Agent：一致性檢查器正在審查...[/cyan]")

        # 截斷過長的草稿
        truncated_draft = draft
        if len(draft) > MAX_DRAFT_LENGTH:
            truncated_draft = draft[:MAX_DRAFT_LENGTH] + "\n...(草稿已截斷，僅檢查前半部分)"

        prompt = f"""You are a Logic Auditor.
Check the consistency of the following document.

# Checks
1. **Subject vs Content**: Does the "Subject" (主旨) accurately summarize the "Explanation" (說明)?
2. **Actionability**: If "Subject" says "Please attend" (請出席), does "Provisions" (辦法) list time and place?
3. **Internal Logic**: Are there contradictions?

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
