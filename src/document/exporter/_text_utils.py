"""Text sanitization and auto-numbering utilities for DOCX export.

Extracted from DocxExporter to keep exporter/__init__.py under the 260-line fat limit.
"""

import re

from src.core.constants import CHINESE_NUMBERS

_RE_CN_NUM = re.compile(r"^[一二三四五六七八九十]{1,3}、")
_RE_CN_SUB = re.compile(r"^[（(][一二三四五六七八九十]{1,3}[）)]")
_RE_ARABIC = re.compile(r"^\d+[.、]")


def sanitize_text(text: str) -> str:
    """清理文字中可能導致 Word 文件損壞的特殊字元。"""
    if not text:
        return ""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"[\ud800-\udfff]", "", text)
    for ch in [
        "\u00a0",
        "\u2000",
        "\u2001",
        "\u2002",
        "\u2003",
        "\u2004",
        "\u2005",
        "\u2006",
        "\u2007",
        "\u2008",
        "\u2009",
        "\u200a",
        "\u202f",
        "\u205f",
        "\u3000",
    ]:
        text = text.replace(ch, " ")
    for ch in [
        "\ufeff",
        "\u200b",
        "\u200c",
        "\u200d",
        "\u200e",
        "\u200f",
        "\u00ad",
        "\u2060",
    ]:
        text = text.replace(ch, "")
    return text


def auto_number(lines: list[str], clean_line_fn) -> list[str]:
    """將多項說明轉換為多層級編號。

    Args:
        lines: Input lines to number.
        clean_line_fn: Callable that strips Markdown/special chars from a line.
    """
    cleaned = [line.rstrip() for line in lines if line.rstrip()]
    if len(cleaned) < 2:
        return lines

    has_existing_numbering = any(
        _RE_CN_NUM.match(clean_line_fn(line))
        or _RE_CN_SUB.match(clean_line_fn(line))
        or _RE_ARABIC.match(clean_line_fn(line))
        for line in cleaned
    )
    if has_existing_numbering:
        return lines

    result: list[str] = []
    level1_idx = 0
    level2_idx = 0
    level3_idx = 0

    for line in lines:
        stripped = line.rstrip()
        if not stripped:
            result.append(line)
            continue

        leading = len(line) - len(line.lstrip())
        effective_indent = leading + line[:leading].count("\t") * 3

        if effective_indent >= 8:
            level3_idx += 1
            result.append(f"{level3_idx}. {stripped.lstrip()}")
        elif effective_indent >= 2:
            prefix = f"（{CHINESE_NUMBERS[level2_idx]}）" if level2_idx < len(CHINESE_NUMBERS) else f"（{level2_idx + 1}）"
            level2_idx += 1
            level3_idx = 0
            result.append(f"{prefix}{stripped.lstrip()}")
        else:
            prefix = f"{CHINESE_NUMBERS[level1_idx]}、" if level1_idx < len(CHINESE_NUMBERS) else f"{level1_idx + 1}、"
            level1_idx += 1
            level2_idx = 0
            level3_idx = 0
            result.append(f"{prefix}{stripped}")

    return result
