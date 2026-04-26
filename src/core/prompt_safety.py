import re


_LLM_ERROR_PATTERN = re.compile(
    r"^("
    r"[Ee]rror\s*:"
    r"|錯誤\s*[：:]"
    r"|错误\s*[：:]"
    r"|I'?m sorry"
    r"|I apologize"
    r"|很抱歉"
    r"|抱歉[，,]?\s*我"
    r"|對不起"
    r"|对不起"
    r"|無法[生完]成"
    r"|无法[生完]成"
    r"|我無法"
    r"|我无法"
    r")",
    re.IGNORECASE,
)


def is_llm_error_response(text: str | None) -> bool:
    """判斷 LLM 回應是否為錯誤訊息或拒絕回覆，而非有效內容。"""
    if not text or not text.strip():
        return True
    return bool(_LLM_ERROR_PATTERN.search(text.strip()))


def escape_prompt_tag(content: str, tag_name: str) -> str:
    """中和內容中的 XML 開頭與結束標籤，防止 prompt injection 突破標籤邊界。"""
    if not content:
        return ""
    result = re.sub(
        rf"</{re.escape(tag_name)}\s*>",
        f"[/{tag_name}]",
        content,
        flags=re.IGNORECASE,
    )
    result = re.sub(
        rf"<{re.escape(tag_name)}(\s[^>]*)?>",
        f"[{tag_name}]",
        result,
        flags=re.IGNORECASE,
    )
    return result
