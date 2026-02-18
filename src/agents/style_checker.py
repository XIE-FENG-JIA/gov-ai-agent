import logging
from rich.console import Console
from src.core.llm import LLMProvider
from src.core.review_models import ReviewResult
from src.core.constants import LLM_TEMPERATURE_PRECISE, MAX_DRAFT_LENGTH
from src.agents.review_parser import parse_review_response

logger = logging.getLogger(__name__)
console = Console()


class StyleChecker:
    """
    檢查公文的語氣、用詞是否正式，是否使用了口語化的表達。
    """

    AGENT_NAME = "Style Checker"
    CATEGORY = "style"

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def check(self, draft: str) -> ReviewResult:
        # 防護空值輸入
        if not draft or not draft.strip():
            logger.warning("StyleChecker 收到空的草稿")
            return ReviewResult(
                agent_name=self.AGENT_NAME, issues=[], score=0.8
            )

        console.print("[cyan]Agent：文風檢查器正在審查...[/cyan]")

        # 截斷過長的草稿
        truncated_draft = draft
        if len(draft) > MAX_DRAFT_LENGTH:
            truncated_draft = draft[:MAX_DRAFT_LENGTH] + "\n...(草稿已截斷，僅檢查前半部分)"

        prompt = f"""You are a strict Government Document Style Editor.
Review the following draft for tone and terminology issues.

# Rules
1. **No Colloquialisms**: Flag words like "幫我", "超棒", "沒問題", "好的". Suggest formal alternatives like "請", "至紉公誼", "無訛", "照辦".
2. **Authoritative Tone**: The text must sound official and objective.
3. **Terminology**: Ensure terms like "台端" (to individual) vs "貴機關" (to agency) are used correctly if context allows.

# Draft
{truncated_draft}

# Output
JSON format only:
{{
    "issues": [
        {{
            "severity": "error/warning/info",
            "location": "string",
            "description": "string",
            "suggestion": "string"
        }}
    ],
    "score": 0.0 to 1.0 (1.0 is perfect)
}}
"""
        response = self.llm.generate(prompt, temperature=LLM_TEMPERATURE_PRECISE)
        return parse_review_response(
            response,
            agent_name=self.AGENT_NAME,
            category=self.CATEGORY,
        )
