import logging

from rich.console import Console
from src.core.llm import LLMProvider
from src.core.models import PublicDocRequirement
from src.core.constants import (
    LLM_TEMPERATURE_CREATIVE,
    KB_WRITER_RESULTS,
    MAX_EXAMPLE_LENGTH,
)
from src.knowledge.manager import KnowledgeBaseManager

logger = logging.getLogger(__name__)
console = Console()


class WriterAgent:
    """
    撰寫 Agent：負責使用 RAG 產生公文初稿。
    """

    def __init__(self, llm_provider: LLMProvider, kb_manager: KnowledgeBaseManager):
        self.llm = llm_provider
        self.kb = kb_manager

    def write_draft(self, requirement: PublicDocRequirement) -> str:
        """
        根據需求和檢索到的範例產生公文草稿。
        """

        # 1. 檢索相關範例（知識庫不可用時優雅降級）
        console.print(f"[cyan]正在搜尋與「{requirement.subject}」相關的範例...[/cyan]")
        query = f"{requirement.doc_type} {requirement.subject}"
        try:
            examples = self.kb.search_examples(query, n_results=KB_WRITER_RESULTS)
        except Exception as exc:
            logger.warning("知識庫搜尋失敗，將不使用範例: %s", exc)
            examples = []

        example_text = ""
        sources_list = []
        if examples:
            console.print(f"[green]找到 {len(examples)} 筆相關範例。[/green]")
            for i, ex in enumerate(examples, 1):
                title = ex.get('metadata', {}).get('title', 'Unknown')
                source_id = f"Source {i}"
                # 截斷過長的範例內容
                content = ex.get('content', '') or ''
                if len(content) > MAX_EXAMPLE_LENGTH:
                    content = content[:MAX_EXAMPLE_LENGTH] + "\n...(內容已截斷)"
                example_text += f"--- {source_id}: {title} ---\n{content}\n\n"
                sources_list.append(f"[^{i}]: {title}")
        else:
            console.print("[yellow]找不到相關範例，將使用通用模板。[/yellow]")

        # 2. Construct Prompt（安全處理 None 值）
        reason_text = requirement.reason or "（未提供）"
        actions_text = ', '.join(requirement.action_items) if requirement.action_items else "（未提供）"
        attachments_text = ', '.join(requirement.attachments) if requirement.attachments else "（無）"

        system_prompt = """You are an expert Taiwan Government Document Writer.
Write a high-quality document draft based on the User Requirement and Reference Examples.

# Rules
1. **Format**: Use standard structure (主旨, 說明, 辦法).
2. **Tone**: Formal and authoritative.
3. **Source Attribution (CRITICAL)**:
   - When you adapt phrasing, logic, or regulations from a "Reference Example", you MUST add a citation `[^i]` at the end of that sentence or section.
   - Example: "依據廢棄物清理法辦理[^1]。"
   - If you combine multiple sources, use `[^1][^2]`.
4. **Reference**: Mimic the style of provided examples but adapt to the requirement.
5. **Output**: Return the document content in Markdown. Do NOT generate the "Reference List" yourself; just use the citation tags in the text.

# Reference Examples
{example_text}
"""

        user_prompt = f"""
# User Requirement
- Type: {requirement.doc_type}
- Sender: {requirement.sender}
- Receiver: {requirement.receiver}
- Subject: {requirement.subject}
- Reason: {reason_text}
- Actions: {actions_text}
- Attachments: {attachments_text}

Please write the full draft with citations now.
"""

        full_prompt = system_prompt.replace("{example_text}", example_text) + user_prompt

        console.print("[cyan]正在產生含引用標記的草稿...[/cyan]")
        draft = self.llm.generate(full_prompt, temperature=LLM_TEMPERATURE_CREATIVE)

        # 檢查 LLM 回傳值
        if not draft or not draft.strip():
            logger.warning("LLM 回傳空的草稿，使用基本模板")
            draft = f"### 主旨\n{requirement.subject}\n\n### 說明\n{reason_text}\n"

        # Append Reference List to the draft manually to ensure accuracy
        if sources_list:
            draft += "\n\n### 參考來源 (AI 引用追蹤)\n" + "\n".join(sources_list)

        return draft
