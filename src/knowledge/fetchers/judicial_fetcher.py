"""司法院裁判書 Fetcher — 從司法院法學資料檢索系統取得裁判書全文。

主要來源：lawsearch.judicial.gov.tw（最新裁判列表）
         + judgment.judicial.gov.tw/FJUD/data.aspx（裁判全文 HTML）

免認證，無需 API Key。
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import requests

from src.knowledge.fetchers.base import BaseFetcher, FetchResult, html_to_markdown
from src.knowledge.fetchers.constants import (
    DEFAULT_JUDICIAL_LIMIT,
    SOURCE_LEVEL_A,
)

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# 最新裁判列表 AJAX 端點
_LAWSEARCH_BASE = "https://lawsearch.judicial.gov.tw/controls"

# 各法院最新裁判端點
_COURT_ENDPOINTS: list[dict] = [
    {"url": f"{_LAWSEARCH_BASE}/GetLatestTPSList.ashx?court=TPA&jbookType=",
     "court": "最高行政法院"},
    {"url": f"{_LAWSEARCH_BASE}/GetLatestTPSList.ashx?court=TPS&jbookType=V",
     "court": "最高法院（民事）"},
    {"url": f"{_LAWSEARCH_BASE}/GetLatestTPSList.ashx?court=TPS&jbookType=M",
     "court": "最高法院（刑事）"},
    {"url": f"{_LAWSEARCH_BASE}/GetLatestJCCList.ashx",
     "court": "憲法法庭"},
]


class JudicialFetcher(BaseFetcher):
    """從司法院法學檢索系統擷取最新裁判書（免認證）。

    使用 lawsearch AJAX 端點取得列表，再從 FJUD 取得裁判全文 HTML。
    """

    def __init__(
        self,
        output_dir: Path | None = None,
        limit: int = DEFAULT_JUDICIAL_LIMIT,
        rate_limit: float = 2.0,
    ) -> None:
        super().__init__(
            output_dir=output_dir or Path("kb_data/regulations/judicial"),
            rate_limit=rate_limit,
        )
        self.limit = limit

    def name(self) -> str:
        return "司法院裁判書"

    def fetch(self) -> list[FetchResult]:
        """取得各法院最新裁判列表，再逐筆取全文。"""
        headers = {"User-Agent": _USER_AGENT}

        # Step 1: 從各法院端點取最新裁判連結
        all_items: list[dict] = []
        for ep in _COURT_ENDPOINTS:
            if len(all_items) >= self.limit:
                break
            try:
                resp = self._request_with_retry(
                    "get", ep["url"], headers=headers, timeout=15,
                )
                data = resp.json()
                links = data.get("li_list", [])
                for link_html in links:
                    item = self._parse_link(link_html, ep["court"])
                    if item:
                        all_items.append(item)
            except (requests.RequestException, ValueError) as exc:
                logger.warning("取得 %s 裁判列表失敗：%s", ep["court"], exc)

        all_items = all_items[: self.limit]

        # Step 2: 逐筆取全文
        results: list[FetchResult] = []
        for item in all_items:
            title = item["title"]
            safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)[:60]
            court = item.get("court", "")
            detail_url = item.get("url", "")

            full_text = ""
            if detail_url:
                try:
                    detail_resp = self._request_with_retry(
                        "get", detail_url, headers=headers, timeout=30,
                    )
                    full_text = self._extract_judgment(detail_resp.text)
                except requests.RequestException as exc:
                    logger.warning("取得裁判全文失敗（%s）：%s", title, exc)

            source_url = detail_url

            body = f"# {title}\n\n"
            if court:
                body += f"**法院**：{court}\n\n"
            if full_text:
                body += f"## 裁判全文\n\n{full_text}\n\n"

            content_hash = self._compute_hash(body)
            metadata = {
                "title": title,
                "doc_type": "裁判書",
                "source": "司法院法學資料檢索系統",
                "court": court,
                "tags": ["裁判書", "司法院"],
                "source_level": SOURCE_LEVEL_A,
                "source_url": source_url,
                "content_hash": content_hash,
            }

            file_path = self.output_dir / f"judicial_{safe_title}.md"
            self._write_markdown(file_path, metadata, body)
            results.append(FetchResult(
                file_path=file_path,
                metadata=metadata,
                collection="regulations",
                source_level=SOURCE_LEVEL_A,
                source_url=source_url,
                content_hash=content_hash,
            ))

        logger.info("JudicialFetcher 擷取完成：%d 個檔案", len(results))
        return results

    # ------------------------------------------------------------------
    # 解析
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_link(link_html: str, court: str) -> dict | None:
        """從 AJAX 回傳的 <a> HTML 提取裁判書連結和標題。"""
        href_m = re.search(r'href="([^"]+)"', link_html)
        text_m = re.search(r'>([^<]+)</a>', link_html)
        if not href_m or not text_m:
            return None
        return {
            "url": href_m.group(1),
            "title": text_m.group(1).strip(),
            "court": court,
        }

    @staticmethod
    def _extract_judgment(html: str) -> str:
        """從 FJUD 裁判書頁面提取主要內容。"""
        # 主要內容在 <div class="htmlcontent"> 內
        m = re.search(
            r'class="htmlcontent">(.*?)</div>\s*</td>',
            html, re.DOTALL,
        )
        if not m:
            # 備用：更寬泛的 htmlcontent 匹配
            m = re.search(
                r'class="htmlcontent">(.*?)</div>\s*</div>\s*</div>',
                html, re.DOTALL,
            )
        if m:
            raw = m.group(1)
            # 清除 HTML 標籤，保留換行
            text = re.sub(r'<(?:div|p|br)[^>]*/?\s*>', '\n', raw, flags=re.IGNORECASE)
            text = re.sub(r'<[^>]+>', '', text)
            text = re.sub(r'&nbsp;', ' ', text)
            text = re.sub(r'\n{3,}', '\n\n', text)
            return text.strip()

        # 退而求其次：取 body
        body_m = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
        if body_m:
            return html_to_markdown(body_m.group(1))

        return ""
