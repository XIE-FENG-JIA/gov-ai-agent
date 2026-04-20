import re

from src.document import REFERENCE_SECTION_HEADING
from src.core.constants import CHINESE_NUMBERS, MAX_CHINESE_NUMBER


def clean_markdown_artifacts(text: str | None) -> str:
    """清除 markdown 格式標記和其他不應出現在公文中的符號"""
    if not text:
        return ""

    text = re.sub(r"```\w*\n?", "", text)
    text = re.sub(r"```", "", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"~~([^~]+)~~", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^---+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"捺印處", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def renumber_provisions(text: str | None) -> str:
    """重新編排辦法段落的編號，使用標準中文編號格式"""
    if not text:
        return ""

    lines = text.split("\n")
    result = []
    main_counter = 0
    sub_counter = 0
    skip_patterns = [
        r"^正本[：:]",
        r"^副本[：:]",
        r"^承辦",
        r"^局長",
        r"^處長",
        r"^科長",
        r"^主任",
        r"^秘書",
        r"^中華民國",
        r"蓋章",
        r"（蓋章）",
    ]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append("")
            continue

        stripped_no_num = re.sub(r"^[\d一二三四五六七八九十]+[、.)]\s*", "", stripped)
        should_skip = False
        for pattern in skip_patterns:
            if re.match(pattern, stripped_no_num):
                should_skip = True
                result.append(stripped_no_num)
                break

        if should_skip:
            continue

        main_match = re.match(r"^[\d一二三四五六七八九十]+[、.)]\s*(.+)", stripped)
        sub_match = re.match(r"^[\(（][\d一二三四五六七八九十]+[\)）][、.]?\s*(.+)", stripped)

        if sub_match:
            sub_counter += 1
            content = sub_match.group(1)
            cn = CHINESE_NUMBERS[sub_counter - 1] if sub_counter <= MAX_CHINESE_NUMBER else sub_counter
            result.append(f"（{cn}）{content}")
        elif main_match:
            main_counter += 1
            sub_counter = 0
            content = main_match.group(1)
            cn = CHINESE_NUMBERS[main_counter - 1] if main_counter <= MAX_CHINESE_NUMBER else main_counter
            result.append(f"{cn}、{content}")
        else:
            result.append(stripped)

    return "\n".join(result)


def _chinese_index(value: int) -> str:
    """Jinja2 自訂過濾器：將阿拉伯數字轉換為中文數字。"""
    idx = value - 1
    if 0 <= idx < MAX_CHINESE_NUMBER:
        return CHINESE_NUMBERS[idx]
    return str(value)


def _build_attachment_ref(attachments: list[str] | None) -> str:
    if not attachments:
        return ""
    if len(attachments) == 1:
        return attachments[0]
    return "如說明"


def _normalize_urgency(urgency: str) -> str:
    if not urgency:
        return "普通件"
    if urgency.endswith("件"):
        return urgency
    return urgency + "件"


def _build_default_doc_number(sender: str, roc_year: int, month: int, day: int) -> str:
    cleaned = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", sender or "")
    prefix = cleaned[:3] if cleaned else "公文"
    return f"{prefix}字第{roc_year:03d}{month:02d}{day:02d}001號"


def _normalize_reference_section(references: str) -> str:
    if not references:
        return ""

    cleaned = references.strip()
    cleaned = re.sub(
        r"^(?:###\s*參考來源(?:\s*\(AI 引用追蹤\))?|\*\*參考來源\*\*)\s*：?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    if not cleaned:
        return ""
    return f"{REFERENCE_SECTION_HEADING}\n{cleaned}"
