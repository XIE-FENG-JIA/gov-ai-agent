"""即時法規引用驗證與政策查詢服務。"""
from __future__ import annotations

import logging
import re
import threading
import time
import defusedxml.ElementTree as ET
from dataclasses import dataclass, field

import requests

from src.knowledge.fetchers.constants import (
    GAZETTE_API_URL,
    LAW_API_URL,
    LAW_DETAIL_URL,
)
from src.core.constants import HTTP_DEFAULT_TIMEOUT
from src.knowledge._realtime_lookup_laws import (
    check_article as _check_article_impl,
    fuzzy_match as _fuzzy_match_impl,
    parse_laws as _parse_laws_impl,
)
from src.knowledge._realtime_lookup_policy import (
    filter_relevant_records as _filter_relevant_records,
    parse_gazette_xml as _parse_gazette_xml,
)

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = HTTP_DEFAULT_TIMEOUT
_MAX_RETRIES = 2
_BACKOFF_BASE = 2

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

def _request_with_retry(url: str, *, timeout: int = _HTTP_TIMEOUT) -> requests.Response:
    """帶重試的 HTTP GET（獨立於 BaseFetcher，供本模組使用）。"""
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
            if "SSL" in str(exc) or "CERTIFICATE" in str(exc):
                logger.error(
                    "SSL 憑證驗證失敗 %s，拒絕降級以防止 MITM 攻擊。"
                    "請確認目標伺服器憑證或網路環境。", url,
                )
                raise
            last_exc = exc
            if attempt < _MAX_RETRIES:
                time.sleep(_BACKOFF_BASE ** attempt)
    raise last_exc  # type: ignore[misc]

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
    _FAILED_CACHE_TTL = 300  # 下載失敗後 5 分鐘內不重試
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
            try:
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
            except (requests.RequestException, OSError, ValueError) as exc:
                logger.warning("法規資料下載失敗，設定空快取避免重複重試：%s", exc)
                # 設定空快取並使用較短 TTL，避免每次請求都阻塞在重試上
                empty_cache = _LawCacheEntry(data={})
                empty_cache.timestamp = time.time() - self._CACHE_TTL + self._FAILED_CACHE_TTL
                LawVerifier._cache = empty_cache

    @staticmethod
    def _parse_laws(data: bytes) -> list[dict]:
        """解析法規 API 回傳（ZIP 或 JSON）。"""
        return _parse_laws_impl(data)

    def _verify_single(self, citation: Citation) -> CitationCheck:
        """驗證單一法規引用。"""
        if LawVerifier._cache is None:
            raise RuntimeError("法規快取未初始化，請先呼叫 _ensure_cache()")
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
        return _check_article_impl(citation, matched_name, cache, CitationCheck)

    @staticmethod
    def _fuzzy_match(
        target: str,
        candidates: object,
    ) -> tuple[str | None, float]:
        """模糊比對法規名稱，回傳最佳匹配和相似度。"""
        return _fuzzy_match_impl(target, candidates)


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
            except (requests.RequestException, OSError, ET.ParseError) as exc:
                logger.warning("公報資料下載失敗：%s", exc)
                RecentPolicyFetcher._cache = _GazetteCacheEntry(records=[])

    @staticmethod
    def _parse_xml(data: bytes) -> list[dict]:
        """解析公報 XML，回傳 Record 字典清單。"""
        root = ET.fromstring(data)
        return _parse_gazette_xml(root)

    @staticmethod
    def _filter_relevant(records: list[dict], query: str) -> list[dict]:
        """按關鍵字過濾公報記錄。"""
        keywords = re.findall(r'[\u4e00-\u9fff]{2,}', query)
        return _filter_relevant_records(records, query, keywords)
