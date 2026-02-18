import json
import re
import logging
from typing import Optional
from rich.console import Console
from src.core.llm import LLMProvider
from src.core.review_models import ReviewResult, ReviewIssue
from src.core.constants import (
    LLM_TEMPERATURE_BALANCED,
    KB_POLICY_RESULTS,
    DEFAULT_COMPLIANCE_SCORE,
    DEFAULT_COMPLIANCE_CONFIDENCE,
    MAX_DRAFT_LENGTH,
)
from src.knowledge.manager import KnowledgeBaseManager

logger = logging.getLogger(__name__)
console = Console()


class ComplianceChecker:
    """
    檢查公文內容是否符合最新政策方針與上級機關指示。
    """

    AGENT_NAME = "Compliance Checker"
    CATEGORY = "compliance"

    def __init__(self, llm: LLMProvider, kb_manager: Optional[KnowledgeBaseManager] = None):
        self.llm = llm
        self.kb_manager = kb_manager

    def _retrieve_policy_context(self, draft: str) -> str:
        """從知識庫檢索與草稿相關的政策文件。"""
        if not self.kb_manager:
            return ""

        try:
            policy_docs = self.kb_manager.search_policies(
                draft, n_results=KB_POLICY_RESULTS
            )
            if policy_docs:
                return "\n\n".join(
                    f"**{doc.get('metadata', {}).get('title', 'Policy')}**:\n"
                    f"{doc.get('content', '')}"
                    for doc in policy_docs
                )
        except Exception as exc:
            console.print(f"[yellow]警告：無法擷取政策上下文：{exc}[/yellow]")

        return ""

    def _build_default_result(self) -> ReviewResult:
        """建立解析失敗時的預設結果。"""
        return ReviewResult(
            agent_name=self.AGENT_NAME,
            issues=[],
            score=DEFAULT_COMPLIANCE_SCORE,
            confidence=DEFAULT_COMPLIANCE_CONFIDENCE,
        )

    def check(self, draft: str) -> ReviewResult:
        # 防護空值輸入
        if not draft or not draft.strip():
            logger.warning("ComplianceChecker 收到空的草稿")
            return self._build_default_result()

        console.print("[cyan]Agent：合規檢查器正在分析政策一致性...[/cyan]")

        policy_context = self._retrieve_policy_context(draft)

        # 截斷過長的草稿
        truncated_draft = draft
        if len(draft) > MAX_DRAFT_LENGTH:
            truncated_draft = draft[:MAX_DRAFT_LENGTH] + "\n...(草稿已截斷，僅檢查前半部分)"

        prompt = f"""你是政策合規審查專員。請檢查以下公文草稿是否符合最新政策方針。

# 檢查重點
1. **政策一致性**: 內容是否抵觸行政院或上級機關的施政方針（如：淨零碳排、資安優先、數位轉型）？
2. **用詞適當性**: 是否使用了過時或不當的政策術語？
3. **政策方向**: 是否與當前政策風向一致（例如：環境永續、創新經濟、資安國安）？

# 相關政策文件
{policy_context if policy_context else "（無法檢索到相關政策，請根據一般常識判斷）"}

# 公文草稿
{truncated_draft}

# 輸出格式
請以 JSON 格式回應：
{{
    "issues": [
        {{
            "severity": "error/warning/info",
            "location": "段落或章節名稱",
            "description": "問題描述",
            "suggestion": "建議修正方式"
        }}
    ],
    "score": 0.0 to 1.0,
    "confidence": 0.0 to 1.0
}}

註：
- severity="error" 表示明顯抵觸政策
- severity="warning" 表示用詞可能過時或不夠精確
- severity="info" 表示建議性改進
"""
        try:
            response = self.llm.generate(prompt, temperature=LLM_TEMPERATURE_BALANCED)
        except Exception as exc:
            console.print(f"[yellow]合規檢查器 LLM 呼叫失敗：{str(exc)[:50]}[/yellow]")
            return self._build_default_result()

        return self._parse_response(response)

    def _parse_response(self, response: str) -> ReviewResult:
        """解析 LLM 回應，合規檢查需要額外處理 risk_level 映射。"""
        if not response or not response.strip():
            return self._build_default_result()

        try:
            match = re.search(r"(\{.*\})", response, re.DOTALL)
            if not match:
                return self._build_default_result()

            data = json.loads(match.group(1))

            issues = []
            for item in data.get("issues", []):
                if not isinstance(item, dict):
                    continue
                severity = item.get("severity", "warning")
                risk_level = (
                    "high" if severity == "error"
                    else "medium" if severity == "warning"
                    else "low"
                )
                issues.append(ReviewIssue(
                    category=self.CATEGORY,
                    severity=severity,
                    risk_level=risk_level,
                    location=item.get("location", "未知"),
                    description=item.get("description", ""),
                    suggestion=item.get("suggestion"),
                ))

            return ReviewResult(
                agent_name=self.AGENT_NAME,
                issues=issues,
                score=data.get("score", DEFAULT_COMPLIANCE_SCORE),
                confidence=data.get("confidence", DEFAULT_COMPLIANCE_CONFIDENCE),
            )
        except json.JSONDecodeError:
            logger.debug("Compliance Checker: 無法解析 LLM 回應中的 JSON")
            return self._build_default_result()
        except Exception as exc:
            console.print(f"[yellow]合規檢查器：{str(exc)[:50]}[/yellow]")
            return self._build_default_result()
