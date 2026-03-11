"""法務部行政函釋 Fetcher — 爬取法務部主管法規查詢系統取得行政函釋。"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import requests

from src.knowledge.fetchers.base import BaseFetcher, FetchResult, html_to_markdown
from src.knowledge.fetchers.constants import (
    DEFAULT_INTERPRETATION_LIMIT,
    MOJLAW_BASE_URL,
    SOURCE_LEVEL_A,
)

logger = logging.getLogger(__name__)

# 網頁爬取用 User-Agent
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


class InterpretationFetcher(BaseFetcher):
    """爬取法務部行政函釋列表及全文。"""

    def __init__(
        self,
        output_dir: Path | None = None,
        limit: int = DEFAULT_INTERPRETATION_LIMIT,
        keyword: str = "",
        rate_limit: float = 2.0,
    ) -> None:
        super().__init__(
            output_dir=output_dir or Path("kb_data/regulations/interpretations"),
            rate_limit=rate_limit,
        )
        self.limit = limit
        self.keyword = keyword

    def name(self) -> str:
        return "法務部行政函釋"

    def fetch(self) -> list[FetchResult]:
        """爬取法務部函釋列表頁，再逐頁取全文。"""
        headers = {"User-Agent": _USER_AGENT}

        # 使用法制司（A0101）的列表頁作為預設
        list_url = f"{MOJLAW_BASE_URL}/LawCategoryContentList.aspx?CID=A0101&type=M"
        params: dict = {}

        try:
            resp = self._request_with_retry(
                "get", list_url, params=params, headers=headers, timeout=30,
            )
        except requests.RequestException as exc:
            logger.error("取得函釋列表失敗：%s", exc)
            return []

        items = self._parse_list_page(resp.text)
        items = items[: self.limit]

        results: list[FetchResult] = []
        for idx, item in enumerate(items):
            title = item.get("title", f"函釋_{idx + 1}")
            safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)[:60]
            detail_url = item.get("url", "")
            date = item.get("date", "")
            ref_no = item.get("ref_no", "")

            # 取全文
            full_text = ""
            if detail_url:
                try:
                    detail_resp = self._request_with_retry(
                        "get", detail_url, headers=headers, timeout=30,
                    )
                    full_text = self._extract_content(detail_resp.text)
                except requests.RequestException as exc:
                    logger.warning("取得函釋全文失敗（%s）：%s", title, exc)

            source_url = detail_url or list_url

            body = f"# {title}\n\n"
            if ref_no:
                body += f"**函釋字號**：{ref_no}\n\n"
            if date:
                body += f"**日期**：{date}\n\n"
            if full_text:
                body += f"## 全文\n\n{full_text}\n\n"

            content_hash = self._compute_hash(body)
            metadata = {
                "title": title,
                "doc_type": "行政函釋",
                "source": "法務部主管法規查詢系統",
                "ref_no": ref_no,
                "date": date,
                "tags": ["函釋", "法務部"],
                "source_level": SOURCE_LEVEL_A,
                "source_url": source_url,
                "content_hash": content_hash,
            }

            file_path = self.output_dir / f"interpretation_{safe_title}.md"
            self._write_markdown(file_path, metadata, body)
            results.append(FetchResult(
                file_path=file_path,
                metadata=metadata,
                collection="regulations",
                source_level=SOURCE_LEVEL_A,
                source_url=source_url,
                content_hash=content_hash,
            ))

        logger.info("InterpretationFetcher 擷取完成：%d 個檔案", len(results))
        return results

    # ------------------------------------------------------------------
    # HTML 解析
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_list_page(html: str) -> list[dict]:
        """從列表頁 HTML 提取函釋項目。"""
        items: list[dict] = []

        # 匹配法規內容連結（LawContent.aspx?LSID=xxx）
        pattern = re.compile(
            r'<a[^>]+href=["\']([^"\']*LawContent\.aspx[^"\']*)["\'][^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        for match in pattern.finditer(html):
            href = match.group(1).strip()
            title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
            if not title:
                continue

            # 處理相對 URL
            if href.startswith("/"):
                href = f"{MOJLAW_BASE_URL}{href}"
            elif not href.startswith("http"):
                href = f"{MOJLAW_BASE_URL}/{href}"

            # 嘗試提取日期和字號
            date_match = re.search(r'(\d{2,4}[./\-]\d{1,2}[./\-]\d{1,2})', title)
            date = date_match.group(1) if date_match else ""

            ref_match = re.search(r'([\u4e00-\u9fff]+字第\s*\d+\s*號)', title)
            ref_no = ref_match.group(1) if ref_match else ""

            items.append({
                "title": title,
                "url": href,
                "date": date,
                "ref_no": ref_no,
            })

        return items

    @staticmethod
    def _extract_content(html: str) -> str:
        """從函釋詳情頁提取主要內容。"""
        # 法務部法規查詢系統使用 law-content-moj class
        content_match = re.search(
            r'<div[^>]*class=["\'][^"\']*law-content[^"\']*["\'][^>]*>(.*?)</div>',
            html, re.DOTALL | re.IGNORECASE,
        )
        if content_match:
            return html_to_markdown(content_match.group(1))

        # 退而求其次：找 content id
        content_match = re.search(
            r'<div[^>]*id=["\']content["\'][^>]*>(.*?)</div>',
            html, re.DOTALL | re.IGNORECASE,
        )
        if content_match:
            return html_to_markdown(content_match.group(1))

        # 退而求其次：取 body 全文
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
        if body_match:
            return html_to_markdown(body_match.group(1))

        return html_to_markdown(html)
