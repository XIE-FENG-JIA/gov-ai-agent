"""主計總處統計 Fetcher — 從主計總處統計發布訊息頁取得國情統計通報。

來源：stat.gov.tw 統計發布訊息（新聞稿列表）
資料：CPI、GDP、就業、人口等公文常引用的統計指標
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import requests

from src.knowledge.fetchers.base import BaseFetcher, FetchResult
from src.knowledge.fetchers.constants import (
    SOURCE_LEVEL_B,
)

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# 統計發布訊息列表頁（國情統計通報）
_STAT_NEWS_URL = "https://www.stat.gov.tw/News.aspx"
# n=3703 是「新聞稿」, n=2720 是「國情統計通報」
_NEWS_PARAMS = {"n": "3703", "sms": "11480"}

DEFAULT_STATISTICS_LIMIT = 10


class StatisticsFetcher(BaseFetcher):
    """從主計總處網站擷取統計發布新聞稿（CPI、GDP、就業等）。"""

    def __init__(
        self,
        output_dir: Path | None = None,
        limit: int = DEFAULT_STATISTICS_LIMIT,
        rate_limit: float = 2.0,
    ) -> None:
        super().__init__(
            output_dir=output_dir or Path("kb_data/policies/statistics"),
            rate_limit=rate_limit,
        )
        self.limit = limit

    def name(self) -> str:
        return "主計總處統計"

    def fetch(self) -> list[FetchResult]:
        """從統計發布訊息頁取得新聞稿列表，再逐頁取內容。"""
        headers = {"User-Agent": _USER_AGENT}

        # Step 1: 取列表頁
        try:
            resp = self._request_with_retry(
                "get", _STAT_NEWS_URL, params=_NEWS_PARAMS,
                headers=headers, timeout=30,
            )
        except requests.RequestException as exc:
            logger.error("取得主計總處統計列表失敗：%s", exc)
            return []

        items = self._parse_list_page(resp.text)
        items = items[: self.limit]

        # Step 2: 逐頁取內容
        results: list[FetchResult] = []
        for item in items:
            title = item["title"]
            safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)[:60]
            detail_url = item["url"]
            date = item.get("date", "")

            content_text = ""
            pdf_urls: list[str] = []
            if detail_url:
                try:
                    detail_resp = self._request_with_retry(
                        "get", detail_url, headers=headers, timeout=30,
                    )
                    content_text, pdf_urls = self._extract_content(detail_resp.text)
                except requests.RequestException as exc:
                    logger.warning("取得統計通報內容失敗（%s）：%s", title, exc)

            source_url = detail_url

            body = f"# {title}\n\n"
            if date:
                body += f"**發布日期**：{date}\n\n"
            body += "**來源**：主計總處統計發布訊息\n\n"
            if content_text:
                body += f"## 內容摘要\n\n{content_text}\n\n"
            if pdf_urls:
                body += "## 附件下載\n\n"
                for pdf_url in pdf_urls:
                    body += f"- {pdf_url}\n"
                body += "\n"

            content_hash = self._compute_hash(body)
            metadata = {
                "title": title,
                "doc_type": "統計資料",
                "source": "主計總處統計發布訊息",
                "date": date,
                "tags": ["統計", "主計總處"],
                "source_level": SOURCE_LEVEL_B,
                "source_url": source_url,
                "content_hash": content_hash,
            }

            file_path = self.output_dir / f"statistics_{safe_title}.md"
            self._write_markdown(file_path, metadata, body)
            results.append(FetchResult(
                file_path=file_path,
                metadata=metadata,
                collection="policies",
                source_level=SOURCE_LEVEL_B,
                source_url=source_url,
                content_hash=content_hash,
            ))

        logger.info("StatisticsFetcher 擷取完成：%d 個檔案", len(results))
        return results

    # ------------------------------------------------------------------
    # HTML 解析
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_list_page(html: str) -> list[dict]:
        """從列表頁提取新聞稿項目。"""
        items: list[dict] = []

        # 匹配 News_Content.aspx 連結
        pattern = re.compile(
            r'<a[^>]+href=["\']([^"\']*News_Content[^"\']*)["\'][^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        for match in pattern.finditer(html):
            href = match.group(1).strip()
            raw_text = match.group(2).strip()
            title = re.sub(r'<[^>]+>', '', raw_text).strip()
            if not title or len(title) < 5:
                continue

            # 嘗試提取日期（格式如 115-03-06）
            date = ""
            date_m = re.match(r'(\d{3}-\d{2}-\d{2})', title)
            if date_m:
                date = date_m.group(1)
                title = title[len(date):].strip()

            if href.startswith("/"):
                href = f"https://www.stat.gov.tw{href}"
            elif not href.startswith("http"):
                href = f"https://www.stat.gov.tw/{href}"

            items.append({"title": title, "url": href, "date": date})

        return items

    @staticmethod
    def _extract_content(html: str) -> tuple[str, list[str]]:
        """從新聞稿詳情頁提取內容摘要和 PDF 連結。

        Returns:
            (content_text, pdf_urls)
        """
        # 找 base-page-area 內容
        content_text = ""
        idx = html.find("base-page-area")
        if idx > 0:
            block = html[idx:idx + 15000]
            # 提取主要文字（排除導航等）
            # 找所有 <p> 或有意義的文字行
            text = re.sub(r'<[^>]+>', '\n', block)
            text = re.sub(r'&nbsp;', ' ', text)
            text = re.sub(r'&lt;', '<', text)
            text = re.sub(r'&gt;', '>', text)
            text = re.sub(r'&amp;', '&', text)
            lines = []
            for line in text.split('\n'):
                line = line.strip()
                # 過濾掉導航、按鈕等短文字
                if len(line) > 10 and not any(k in line for k in [
                    'Bopomofo', 'base-', 'group-', 'list-text',
                    'javascript:', 'data-index',
                ]):
                    lines.append(line)
            content_text = '\n'.join(lines)

        # 找 PDF 連結
        pdf_urls = re.findall(
            r'href=["\']([^"\']*\.pdf)["\']',
            html, re.IGNORECASE,
        )

        return content_text, pdf_urls
