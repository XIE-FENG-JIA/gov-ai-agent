import json
import logging
import re
from typing import Optional

from rich.console import Console

from src.core.llm import LLMProvider
from src.core.models import PublicDocRequirement
from src.core.constants import LLM_TEMPERATURE_PRECISE, MAX_USER_INPUT_LENGTH

logger = logging.getLogger(__name__)
console = Console()


def _sanitize_json_string(text: Optional[str]) -> str:
    """
    清理 LLM 回應中可能導致 JSON 解析失敗的特殊字元。

    處理：
    - 未轉義的換行符（在 JSON 字串值內）
    - 未轉義的制表符
    - 控制字元
    """
    if not text:
        return ""
    # 移除 BOM 和零寬度字元
    text = text.replace('\ufeff', '').replace('\u200b', '')
    return text


class RequirementAgent:
    """
    需求分析 Agent：負責分析使用者輸入並擷取結構化的公文需求。
    """

    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider

    def analyze(self, user_input: str) -> PublicDocRequirement:
        """
        分析自然語言輸入並回傳結構化的需求物件。

        Raises:
            ValueError: 當輸入為空或 LLM 回傳無法解析的結果時
        """
        # 驗證輸入不為空
        if not user_input or not user_input.strip():
            raise ValueError("使用者輸入不可為空白。請提供公文需求描述。")

        # 截斷過長的輸入
        user_input = user_input.strip()
        if len(user_input) > MAX_USER_INPUT_LENGTH:
            logger.warning(
                "使用者輸入過長（%d 字元），已截斷至 %d 字元",
                len(user_input), MAX_USER_INPUT_LENGTH,
            )
            user_input = user_input[:MAX_USER_INPUT_LENGTH]

        system_prompt = """You are an expert Taiwan Government Document Secretary.
Extract structured requirements from the user's request into JSON format.

# Schema
{
    "doc_type": "函 or 公告 or 簽",
    "urgency": "普通 or 速件 or 最速件",
    "sender": "Sending agency name (e.g. 臺北市政府)",
    "receiver": "Receiving agency (e.g. 各區公所)",
    "subject": "Summary of the request (Traditional Chinese)",
    "reason": "Reason/Context (Traditional Chinese)",
    "action_items": ["Action 1", "Action 2"],
    "attachments": ["Attachment Name"]
}

# Example
Input: "幫我寫一份函，台北市環保局要發給各學校，關於加強資源回收，附件是回收指南。"
Output:
{
    "doc_type": "函",
    "urgency": "普通",
    "sender": "臺北市政府環境保護局",
    "receiver": "臺北市各級學校",
    "subject": "函轉有關加強校園資源回收工作一案，請查照。",
    "reason": "為提升本市資源回收成效，落實環境教育。",
    "action_items": ["請加強宣導", "落實分類"],
    "attachments": ["校園資源回收指南"]
}

# Task
User Request: {user_input}
Output JSON (Traditional Chinese):"""
        
        prompt = system_prompt.replace("{user_input}", user_input)
        
        console.print("[cyan]正在分析需求...[/cyan]")
        response_text = self.llm.generate(prompt, temperature=LLM_TEMPERATURE_PRECISE)

        # 檢查 LLM 是否回傳了錯誤訊息或空值
        if not response_text or not response_text.strip():
            raise ValueError("LLM 回傳空的回應。請檢查 LLM 服務是否正常運作。")

        if response_text.startswith("Error"):
            raise ValueError(f"LLM 呼叫失敗: {response_text}")

        # 清理可能的特殊字元
        response_text = _sanitize_json_string(response_text)

        # Robust JSON Extraction Strategy

        # 1. Try to find JSON inside Markdown code blocks
        code_block_pattern = r"```(?:json)?\s*(.*?)\s*```"
        matches = re.findall(code_block_pattern, response_text, re.DOTALL)

        for match in matches:
            try:
                data = json.loads(match)
                return PublicDocRequirement(**data)
            except (json.JSONDecodeError, ValueError, TypeError) as exc:
                logger.debug("JSON 解析策略 1 (code block) 失敗: %s", exc)
                continue

        # 2. Fallback: Try to find the outermost JSON object using balanced brace matching
        try:
            start_idx = response_text.find('{')
            if start_idx != -1:
                # 使用平衡括號匹配，而非簡單的 rfind
                depth = 0
                end_idx = -1
                for i in range(start_idx, len(response_text)):
                    if response_text[i] == '{':
                        depth += 1
                    elif response_text[i] == '}':
                        depth -= 1
                        if depth == 0:
                            end_idx = i
                            break

                if end_idx != -1:
                    json_str = response_text[start_idx : end_idx + 1]
                    data = json.loads(json_str)
                    return PublicDocRequirement(**data)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.debug("JSON 解析策略 2 (balanced braces) 失敗: %s", exc)

        # 3. Last resort: Try to extract individual fields via regex
        try:
            doc_type_m = re.search(r'"doc_type"\s*:\s*"([^"]+)"', response_text)
            sender_m = re.search(r'"sender"\s*:\s*"([^"]+)"', response_text)
            receiver_m = re.search(r'"receiver"\s*:\s*"([^"]+)"', response_text)
            subject_m = re.search(r'"subject"\s*:\s*"([^"]+)"', response_text)
            if doc_type_m and sender_m and receiver_m and subject_m:
                return PublicDocRequirement(
                    doc_type=doc_type_m.group(1),
                    sender=sender_m.group(1),
                    receiver=receiver_m.group(1),
                    subject=subject_m.group(1),
                )
        except (ValueError, TypeError) as exc:
            logger.debug("JSON 解析策略 3 (regex fields) 失敗: %s", exc)

        console.print(f"[bold red]無法從 LLM 回應中解析 JSON：[/bold red]\n{response_text[:200]}")
        raise ValueError("LLM 未回傳有效的 JSON。請檢查模型輸出內容。")
