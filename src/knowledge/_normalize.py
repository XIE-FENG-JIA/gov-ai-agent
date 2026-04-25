"""法規引用正規化、提取與格式化 — 供 realtime_lookup 模組使用。"""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.knowledge.fetchers.constants import LAW_DETAIL_URL


# ---- Dataclasses ----

@dataclass
class Citation:
    """從草稿中解析出的法規引用。"""
    law_name: str
    article_no: str | None
    original_text: str
    location: str


@dataclass
class CitationCheck:
    """單一引用的驗證結果。"""
    citation: Citation
    law_exists: bool
    article_exists: bool | None
    actual_content: str | None
    pcode: str | None
    confidence: float
    closest_match: str | None = None


# ---- Citation patterns ----

# 法規引用正則（含前綴動詞）
_CITATION_PATTERN = re.compile(
    r'(?:依據|依|按|遵照|援引)\s*[「「]?'
    r'(.{2,30}?(?:法|條例|辦法|規則|細則|規程|標準|準則|綱要|通則))'
    r'[」」]?\s*'
    r'(?:第\s*(\d+(?:-\d+)?)\s*條)?'
)

# 獨立法規+條文引用（無前綴動詞，但有明確「第X條」）
_STANDALONE_CITATION_PATTERN = re.compile(
    r'[「「]?([\u4e00-\u9fff]{2,20}(?:法|條例|辦法|規則|細則|規程|標準|準則|綱要|通則))[」」]?'
    r'\s*第\s*(\d+(?:-\d+)?)\s*條'
)


def extract_citations(text: str) -> list[Citation]:
    """從文字中提取所有法規引用（主模式 + 獨立模式，去重）。"""
    seen: set[tuple[str, str | None]] = set()
    matched_spans: set[tuple[int, int, int]] = set()  # (line_no, start, end)
    results: list[Citation] = []

    lines = text.split("\n")
    for line_no, line in enumerate(lines, 1):
        # 第一輪：主要模式（含前綴動詞）
        for m in _CITATION_PATTERN.finditer(line):
            matched_spans.add((line_no, m.start(), m.end()))
            law_name = m.group(1).strip()
            article_no = m.group(2)
            key = (law_name, article_no)
            if key not in seen:
                seen.add(key)
                results.append(Citation(
                    law_name=law_name,
                    article_no=article_no,
                    original_text=m.group(0).strip(),
                    location=f"第 {line_no} 行",
                ))

        # 第二輪：獨立模式，跳過與主模式有重疊的位置
        for m in _STANDALONE_CITATION_PATTERN.finditer(line):
            if any(
                not (m.end() <= s or m.start() >= e)
                for ln, s, e in matched_spans
                if ln == line_no
            ):
                continue
            law_name = m.group(1).strip()
            article_no = m.group(2)
            key = (law_name, article_no)
            if key not in seen:
                seen.add(key)
                results.append(Citation(
                    law_name=law_name,
                    article_no=article_no,
                    original_text=m.group(0).strip(),
                    location=f"第 {line_no} 行",
                ))

    return results


def format_verification_results(checks: list[CitationCheck]) -> str:
    """將驗證結果格式化為 prompt 內嵌文字。"""
    if not checks:
        return ""

    lines = ["## 即時法規驗證結果（來源：全國法規資料庫 API）\n"]

    for chk in checks:
        c = chk.citation
        if chk.law_exists:
            law_url = LAW_DETAIL_URL.format(pcode=chk.pcode) if chk.pcode else ""
            url_note = f"\n  🔗 {law_url}" if law_url else ""

            if chk.closest_match and chk.closest_match != c.law_name:
                lines.append(
                    f"⚠️ {c.law_name} → 最相似法規：「{chk.closest_match}」{url_note}"
                )
            else:
                lines.append(f"✅ {c.law_name} — 法規存在{url_note}")

            if chk.article_exists is True and c.article_no:
                content_preview = (chk.actual_content or "")[:100]
                lines.append(f"  ✅ 第 {c.article_no} 條 — 條文存在：「{content_preview}」")
            elif chk.article_exists is False and c.article_no:
                extra = f"（{chk.actual_content}）" if chk.actual_content else ""
                lines.append(
                    f"  ❌ 第 {c.article_no} 條 — 條文不存在{extra}"
                )
        else:
            lines.append(f"❌ {c.law_name} — 全國法規資料庫中查無此法規名稱")
            if chk.closest_match:
                lines.append(f"  → 最相似法規：「{chk.closest_match}」")

    return "\n".join(lines)
