"""XML parsing helpers for LawFetcher bulk downloads."""

from __future__ import annotations

import re

import defusedxml.ElementTree as ET


def parse_bulk_xml(data: bytes) -> list[dict]:
    """解析全國法規資料庫 bulk XML，回傳與 JSON API 相同格式的 dict 清單。"""
    text = _decode_xml(data)
    root = ET.fromstring(text)
    laws: list[dict] = []

    for law_elem in list(root.iter("法規")) + list(root.iter("Law")):
        law_dict = _parse_law_element(law_elem)
        if law_dict is not None:
            laws.append(law_dict)

    return laws


def _decode_xml(data: bytes) -> str:
    for encoding in ("utf-8", "big5", "cp950"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


def _find_text(element, *names: str) -> str:
    for name in names:
        found = element.find(name)
        if found is not None and found.text:
            return found.text.strip()
    return ""


def _parse_law_element(law_elem) -> dict | None:
    law_dict: dict = {}

    law_name = _find_text(law_elem, "法規名稱", "LawName")
    if law_name:
        law_dict["LawName"] = law_name

    url_text = _find_text(law_elem, "法規網址", "LawURL")
    if url_text:
        pcode_match = re.search(r"pcode=([A-Z0-9]+)", url_text, re.IGNORECASE)
        if pcode_match:
            law_dict["PCode"] = pcode_match.group(1)

    pcode = _find_text(law_elem, "PCode")
    if pcode:
        law_dict["PCode"] = pcode

    if "PCode" not in law_dict:
        return None

    law_dict["LawArticles"] = _parse_articles(law_elem)
    return law_dict


def _parse_articles(law_elem) -> list[dict]:
    articles: list[dict] = []
    foreword_text = _find_text(law_elem, "前言", "Foreword")
    if foreword_text:
        articles.append({"ArticleNo": "前言", "ArticleContent": foreword_text})

    for art_elem in list(law_elem.iter("條文")) + list(law_elem.iter("Article")):
        art_no = _find_text(art_elem, "條號", "ArticleNo")
        art_content = _find_text(art_elem, "條文內容", "ArticleContent")
        if art_no or art_content:
            articles.append({"ArticleNo": art_no, "ArticleContent": art_content})

    return articles
