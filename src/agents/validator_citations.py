"""Citation validation helpers for public-document drafts."""

import re
from collections.abc import Callable

IssueFactory = Callable[[str, str, str | None], dict]


def check_citation_level(draft_text: str, issue: IssueFactory) -> list[dict]:
    """檢查引用等級合規性：Level A 權威來源、待補依據標記。"""
    errors: list[dict] = []

    pending_count = draft_text.count("【待補依據】")
    if pending_count > 0:
        errors.append(issue(
            f"草稿包含 {pending_count} 處「待補依據」標記，需補充 Level A 權威來源。",
            "待補依據標記",
            "使用 gov-ai kb search 查詢相關法規，以 Level A 權威來源（公報/法規）替換「【待補依據】」",
        ))

    ref_section_match = re.search(r"###\s*參考來源.*", draft_text, re.DOTALL)
    if ref_section_match:
        ref_section = ref_section_match.group(0)
        if "[Level A]" not in ref_section:
            errors.append(issue(
                "參考來源中缺少 Level A 權威來源（公報/法規），建議補充。",
                "參考來源段落",
                "補充至少一筆 Level A 來源（如全國法規資料庫、行政院公報），標記為 [Level A]",
            ))

    yiju_matches = re.finditer(r"依據[^。\n]{2,30}(?:辦理|規定|處理|執行)", draft_text)
    for match in yiju_matches:
        end_pos = match.end()
        trailing = draft_text[end_pos:end_pos + 15]
        matched_text = match.group(0)
        if "[^" not in trailing and "【待補依據】" not in trailing and "[^" not in draft_text[match.start():end_pos]:
            errors.append(issue(
                f"法律主張「{matched_text}」缺少引用標記 [^n] 或「待補依據」。",
                f"「{matched_text}」",
                f"在「{matched_text}」後方加入引用標記（如 [^1]），並在參考來源段落補充對應定義",
            ))

    return errors


def check_evidence_presence(draft_text: str, issue: IssueFactory) -> list[dict]:
    """檢查草稿是否包含至少一個 evidence-backed 引用。"""
    errors: list[dict] = []
    if "參考來源" not in draft_text:
        errors.append(issue(
            "草稿缺少「參考來源」段落，無法驗證引用來源。",
            "文件結構",
            "在文末新增「### 參考來源」段落，列出引用的法規與公報來源",
        ))
    if not re.search(r"\[\^(\d+)\]", draft_text):
        errors.append(issue(
            "草稿中無任何引用標記 [^n]，建議補充 evidence-backed 引用。",
            "引用標記",
            "在法規依據處加入 [^1] 等標記，並在參考來源段落定義 [^1]: 來源名稱",
        ))
    return errors


def check_citation_integrity(draft_text: str, issue: IssueFactory) -> list[dict]:
    """檢查引用完整性：找出孤兒引用與未使用定義。"""
    errors: list[dict] = []
    inline_refs = set(re.findall(r"\[\^(\d+)\](?!:)", draft_text))
    definitions = set(re.findall(r"\[\^(\d+)\]:", draft_text))

    for ref_id in sorted(inline_refs - definitions, key=int):
        errors.append(issue(
            f"孤兒引用：[^{ref_id}] 在文中被引用，但缺少對應的參考來源定義。",
            f"引用 [^{ref_id}]",
            f"在參考來源段落新增「[^{ref_id}]: 來源名稱與連結」",
        ))

    for def_id in sorted(definitions - inline_refs, key=int):
        errors.append(issue(
            f"未使用定義：[^{def_id}] 已定義但未在文中引用，建議移除或補充引用。",
            f"定義 [^{def_id}]",
            f"在文中適當位置加入 [^{def_id}] 引用，或從參考來源段落移除該定義",
        ))

    return errors
