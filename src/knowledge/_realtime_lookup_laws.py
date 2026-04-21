from __future__ import annotations

import io
import json
import logging
import re
import zipfile
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


def parse_laws(data: bytes) -> list[dict]:
    """解析法規 API 回傳（ZIP 或 JSON）。"""
    raw_list: list[dict] = []

    def _unwrap(parsed):
        if isinstance(parsed, dict):
            if "Laws" in parsed and isinstance(parsed["Laws"], list):
                return parsed["Laws"]
            return [parsed]
        if isinstance(parsed, list):
            return parsed
        return []

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for name in zf.namelist():
                if not name.endswith(".json"):
                    continue
                raw = zf.read(name)
                try:
                    parsed = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    logger.warning("ZIP 內 JSON 解析失敗：%s", name)
                    continue
                raw_list.extend(_unwrap(parsed))
    except zipfile.BadZipFile:
        try:
            parsed = json.loads(data)
        except (json.JSONDecodeError, ValueError):
            logger.warning("法規 API 回傳資料非合法 ZIP 亦非合法 JSON（%d bytes）", len(data))
            return raw_list
        raw_list.extend(_unwrap(parsed))

    for law in raw_list:
        if "PCode" in law:
            continue
        url = law.get("LawURL", "")
        match = re.search(r"pcode=([A-Z0-9]+)", url, re.IGNORECASE)
        if match:
            law["PCode"] = match.group(1)

    return raw_list


def check_article(citation, matched_name: str, cache: dict[str, dict], citation_check_cls):
    """法規已確認存在，進一步檢查條文號。"""
    law_data = cache[matched_name]
    pcode = law_data["pcode"]
    articles = law_data["articles"]

    if citation.article_no is None:
        return citation_check_cls(
            citation=citation,
            law_exists=True,
            article_exists=None,
            actual_content=None,
            pcode=pcode,
            confidence=1.0,
        )

    normalized_art = re.sub(r"[第條\s]", "", citation.article_no)

    if normalized_art in articles:
        return citation_check_cls(
            citation=citation,
            law_exists=True,
            article_exists=True,
            actual_content=articles[normalized_art],
            pcode=pcode,
            confidence=1.0,
        )

    max_art = max(
        (int(re.sub(r"-.*", "", key)) for key in articles if re.match(r"\d+", key)),
        default=0,
    )
    return citation_check_cls(
        citation=citation,
        law_exists=True,
        article_exists=False,
        actual_content=f"此法規共 {max_art} 條" if max_art > 0 else None,
        pcode=pcode,
        confidence=0.0,
    )


def fuzzy_match(target: str, candidates: object) -> tuple[str | None, float]:
    """模糊比對法規名稱，回傳最佳匹配和相似度。"""
    best_name: str | None = None
    best_ratio = 0.0

    for name in candidates:
        shorter = min(len(target), len(name))
        if shorter >= 2 and (target in name or name in target):
            ratio = len(min(target, name, key=len)) / len(max(target, name, key=len))
            ratio = max(ratio, 0.8)
        else:
            ratio = SequenceMatcher(None, target, name).ratio()

        if ratio > best_ratio:
            best_ratio = ratio
            best_name = name

    return best_name, best_ratio
