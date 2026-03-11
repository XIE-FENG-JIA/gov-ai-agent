"""即時法規引用驗證與政策查詢服務。

LawVerifier: 下載全國法規資料庫全量資料，快取於記憶體，
            從草稿中提取法規引用並逐一比對驗證。

RecentPolicyFetcher: 下載近期行政院公報 XML，
                     按關鍵字過濾後回傳相關政策摘要。
"""
from __future__ import annotations

import io
import json
import logging
import re
import threading
import time
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from difflib import SequenceMatcher

import requests
import urllib3

from src.knowledge.fetchers.constants import (
    GAZETTE_API_URL,
    LAW_API_URL,
    LAW_DETAIL_URL,
)
from src.core.constants import HTTP_DEFAULT_TIMEOUT

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# 台灣政府 API SSL 問題
_GOV_SSL_DOMAINS = frozenset({
    "law.moj.gov.tw",
    "gazette.nat.gov.tw",
})

_HTTP_TIMEOUT = HTTP_DEFAULT_TIMEOUT
_MAX_RETRIES = 2
_BACKOFF_BASE = 2


# ---------------------------------------------------------------------------
# 資料類別
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# HTTP 工具
# ---------------------------------------------------------------------------

def _request_with_retry(url: str, *, timeout: int = _HTTP_TIMEOUT) -> requests.Response:
    """帶重試的 HTTP GET（獨立於 BaseFetcher，供本模組使用）。"""
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    verify = host not in _GOV_SSL_DOMAINS

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = requests.get(url, timeout=timeout, verify=verify)
            resp.raise_for_status()
            return resp
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                time.sleep(_BACKOFF_BASE ** attempt)
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# LawVerifier
# ---------------------------------------------------------------------------

# 法規引用正則
_CITATION_PATTERN = re.compile(
    r'(?:依據|依|按|遵照|援引)\s*[「「]?'
    r'(.{2,30}?(?:法|條例|辦法|規則|細則|規程|標準|準則|綱要|通則))'
    r'[」」]?\s*'
    r'(?:第\s*(\d+(?:-\d+)?)\s*條)?'
)

# 獨立法規+條文引用（無前綴動詞，但有明確「第X條」）
# 限制法規名稱只能含中文字元，避免匹配到標點或無關文字
_STANDALONE_CITATION_PATTERN = re.compile(
    r'[「「]?([\u4e00-\u9fff]{2,20}(?:法|條例|辦法|規則|細則|規程|標準|準則|綱要|通則))[」」]?'
    r'\s*第\s*(\d+(?:-\d+)?)\s*條'
)


@dataclass
class _LawCacheEntry:
    """模組級法規快取。"""
    data: dict[str, dict]  # {law_name: {"pcode": str, "articles": {art_no: content}}}
    timestamp: float = field(default_factory=time.time)


class LawVerifier:
    """即時法規引用驗證器 — 下載全國法規資料庫並快取。"""

    _CACHE_TTL = 86400  # 24 小時
    _cache: _LawCacheEntry | None = None  # 類別級快取，跨實例共享
    _cache_lock = threading.Lock()  # 防止多執行緒同時下載

    def verify_citations(self, draft: str) -> list[CitationCheck]:
        """從草稿提取所有法規引用並逐一驗證。"""
        citations = self._extract_citations(draft)
        if not citations:
            return []

        self._ensure_cache()
        return [self._verify_single(c) for c in citations]

    def _extract_citations(self, text: str) -> list[Citation]:
        """用正則從文字中提取法規引用。"""
        seen: set[tuple[str, str | None]] = set()
        matched_spans: set[tuple[int, int, int]] = set()  # (line_no, start, end)
        results: list[Citation] = []

        lines = text.split("\n")
        for line_no, line in enumerate(lines, 1):
            # 第一輪：主要模式（含前綴動詞）
            for m in _CITATION_PATTERN.finditer(line):
                # 記錄 span（即使 dedup 跳過，也要阻止 standalone 重複匹配）
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

            # 第二輪：獨立模式（無前綴動詞），跳過與主模式有任何重疊的位置
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

    def _ensure_cache(self) -> None:
        """下載並快取全國法規目錄（執行緒安全，double-check locking）。"""
        # 快速路徑：快取有效時不加鎖
        now = time.time()
        if (
            LawVerifier._cache is not None
            and (now - LawVerifier._cache.timestamp) < self._CACHE_TTL
        ):
            return

        with LawVerifier._cache_lock:
            # Double-check：進入鎖後再確認一次（避免多執行緒重複下載）
            now = time.time()
            if (
                LawVerifier._cache is not None
                and (now - LawVerifier._cache.timestamp) < self._CACHE_TTL
            ):
                return

            logger.info("正在下載全國法規資料庫（首次載入約需 3 秒）...")
            resp = _request_with_retry(LAW_API_URL, timeout=120)

            laws = self._parse_laws(resp.content)
            cache_data: dict[str, dict] = {}

            for law in laws:
                law_name = law.get("LawName", "")
                pcode = law.get("PCode", "")
                if not law_name or not pcode:
                    continue

                articles: dict[str, str] = {}
                for art in law.get("LawArticles", []):
                    art_no = art.get("ArticleNo", art.get("Number", ""))
                    content = art.get("ArticleContent", art.get("Content", ""))
                    if art_no and content:
                        # 正規化條文號：「第 32 條」→ "32"
                        normalized = re.sub(r'[第條\s]', '', art_no)
                        articles[normalized] = content

                cache_data[law_name] = {"pcode": pcode, "articles": articles}

            LawVerifier._cache = _LawCacheEntry(data=cache_data)
            logger.info("法規快取載入完成：%d 部法規", len(cache_data))

    @staticmethod
    def _parse_laws(data: bytes) -> list[dict]:
        """解析法規 API 回傳（ZIP 或 JSON）— 重用 LawFetcher 的邏輯。"""
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
                    if name.endswith(".json"):
                        raw = zf.read(name)
                        parsed = json.loads(raw)
                        raw_list.extend(_unwrap(parsed))
        except zipfile.BadZipFile:
            parsed = json.loads(data)
            raw_list.extend(_unwrap(parsed))

        # 從 LawURL 提取 PCode
        for law in raw_list:
            if "PCode" not in law:
                url = law.get("LawURL", "")
                m = re.search(r"pcode=([A-Z0-9]+)", url, re.IGNORECASE)
                if m:
                    law["PCode"] = m.group(1)

        return raw_list

    def _verify_single(self, citation: Citation) -> CitationCheck:
        """驗證單一法規引用。"""
        assert LawVerifier._cache is not None
        cache = LawVerifier._cache.data

        # 精確比對
        if citation.law_name in cache:
            return self._check_article(citation, citation.law_name, cache)

        # 模糊比對（處理「空氣污染防制法」vs「空氣污染防制法施行細則」）
        best_name, best_ratio = self._fuzzy_match(citation.law_name, cache.keys())
        if best_name and best_ratio >= 0.75:
            result = self._check_article(citation, best_name, cache)
            result.closest_match = best_name if best_name != citation.law_name else None
            if best_ratio < 1.0:
                result.confidence *= best_ratio
            return result

        # 查無此法規
        closest = best_name if best_name and best_ratio >= 0.5 else None
        return CitationCheck(
            citation=citation,
            law_exists=False,
            article_exists=None,
            actual_content=None,
            pcode=None,
            confidence=0.0,
            closest_match=closest,
        )

    @staticmethod
    def _check_article(
        citation: Citation,
        matched_name: str,
        cache: dict[str, dict],
    ) -> CitationCheck:
        """法規已確認存在，進一步檢查條文號。"""
        law_data = cache[matched_name]
        pcode = law_data["pcode"]
        articles = law_data["articles"]

        if citation.article_no is None:
            return CitationCheck(
                citation=citation,
                law_exists=True,
                article_exists=None,
                actual_content=None,
                pcode=pcode,
                confidence=1.0,
            )

        # 正規化引用條文號
        normalized_art = re.sub(r'[第條\s]', '', citation.article_no)

        if normalized_art in articles:
            return CitationCheck(
                citation=citation,
                law_exists=True,
                article_exists=True,
                actual_content=articles[normalized_art],
                pcode=pcode,
                confidence=1.0,
            )

        # 條文號不存在
        max_art = max(
            (int(re.sub(r'-.*', '', k)) for k in articles if re.match(r'\d+', k)),
            default=0,
        )
        return CitationCheck(
            citation=citation,
            law_exists=True,
            article_exists=False,
            actual_content=f"此法規共 {max_art} 條" if max_art > 0 else None,
            pcode=pcode,
            confidence=0.0,
        )

    @staticmethod
    def _fuzzy_match(
        target: str,
        candidates: object,
    ) -> tuple[str | None, float]:
        """模糊比對法規名稱，回傳最佳匹配和相似度。"""
        best_name: str | None = None
        best_ratio = 0.0

        for name in candidates:
            # 優先檢查包含關係
            if target in name or name in target:
                ratio = len(min(target, name, key=len)) / len(max(target, name, key=len))
                ratio = max(ratio, 0.8)  # 包含關係至少給 0.8
            else:
                ratio = SequenceMatcher(None, target, name).ratio()

            if ratio > best_ratio:
                best_ratio = ratio
                best_name = name

        return best_name, best_ratio


def format_verification_results(checks: list[CitationCheck]) -> str:
    """將驗證結果格式化為 prompt 內嵌文字。"""
    if not checks:
        return ""

    lines = ["## 即時法規驗證結果（來源：全國法規資料庫 API）\n"]

    for chk in checks:
        c = chk.citation
        if chk.law_exists:
            law_url = LAW_DETAIL_URL.format(pcode=chk.pcode) if chk.pcode else ""
            pcode_note = f"（PCode: {chk.pcode}）" if chk.pcode else ""

            if chk.closest_match and chk.closest_match != c.law_name:
                lines.append(f"⚠️ {c.law_name} → 最相似法規：「{chk.closest_match}」{pcode_note}")
            else:
                lines.append(f"✅ {c.law_name}{pcode_note} — 法規存在")

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


# ---------------------------------------------------------------------------
# RecentPolicyFetcher
# ---------------------------------------------------------------------------

@dataclass
class _GazetteCacheEntry:
    """公報快取。"""
    records: list[dict]
    timestamp: float = field(default_factory=time.time)


class RecentPolicyFetcher:
    """即時政策資料擷取器 — 取得最近的行政院公報。"""

    _CACHE_TTL = 3600  # 1 小時
    _cache: _GazetteCacheEntry | None = None
    _cache_lock = threading.Lock()

    def fetch_recent_policies(self, query: str, days: int = 3) -> str:
        """取得最近公報中與 query 相關的條目。"""
        self._ensure_cache()
        if not RecentPolicyFetcher._cache:
            return ""

        records = RecentPolicyFetcher._cache.records
        if not records:
            return ""

        # 按關鍵字過濾
        relevant = self._filter_relevant(records, query)
        if not relevant:
            return ""

        # 格式化輸出（最多 10 筆）
        lines: list[str] = []
        for rec in relevant[:10]:
            title = rec.get("Title", "無標題")
            category = rec.get("Category", "")
            pub_gov = rec.get("PubGov", "")
            date_pub = rec.get("Date_Published", "")
            lines.append(
                f"- **{title}**（{category}）\n"
                f"  發布機關：{pub_gov}　日期：{date_pub}"
            )

        return "\n".join(lines)

    def _ensure_cache(self) -> None:
        """下載並快取公報資料（執行緒安全，double-check locking）。"""
        now = time.time()
        if (
            RecentPolicyFetcher._cache is not None
            and (now - RecentPolicyFetcher._cache.timestamp) < self._CACHE_TTL
        ):
            return

        with RecentPolicyFetcher._cache_lock:
            now = time.time()
            if (
                RecentPolicyFetcher._cache is not None
                and (now - RecentPolicyFetcher._cache.timestamp) < self._CACHE_TTL
            ):
                return

            logger.info("正在下載行政院公報資料...")
            try:
                resp = _request_with_retry(GAZETTE_API_URL, timeout=60)
                records = self._parse_xml(resp.content)
                RecentPolicyFetcher._cache = _GazetteCacheEntry(records=records)
                logger.info("公報快取載入完成：%d 筆記錄", len(records))
            except Exception as exc:
                logger.warning("公報資料下載失敗：%s", exc)
                RecentPolicyFetcher._cache = _GazetteCacheEntry(records=[])

    @staticmethod
    def _parse_xml(data: bytes) -> list[dict]:
        """解析公報 XML，回傳 Record 字典清單。"""
        root = ET.fromstring(data)
        records: list[dict] = []
        for record_elem in root.iter("Record"):
            rec: dict[str, str] = {}
            for child in record_elem:
                rec[child.tag] = child.text or ""
            records.append(rec)
        return records

    @staticmethod
    def _filter_relevant(records: list[dict], query: str) -> list[dict]:
        """按關鍵字過濾公報記錄。"""
        if not query:
            return records[:10]

        # 抽取關鍵字（去除常見停用詞）
        keywords = re.findall(r'[\u4e00-\u9fff]{2,}', query)
        if not keywords:
            return records[:10]

        scored: list[tuple[int, dict]] = []
        for rec in records:
            title = rec.get("Title", "")
            category = rec.get("Category", "")
            text = f"{title} {category}"
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scored.append((score, rec))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [rec for _, rec in scored]
