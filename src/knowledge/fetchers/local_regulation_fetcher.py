"""地方法規 Fetcher — 爬取各縣市法規網站取得地方法規。"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import requests

from src.knowledge.fetchers.base import BaseFetcher, FetchResult, html_to_markdown
from src.knowledge.fetchers.constants import (
    DEFAULT_LOCAL_LIMIT,
    LOCAL_LAW_URLS,
    SOURCE_LEVEL_A,
)

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


class LocalRegulationFetcher(BaseFetcher):
    """爬取地方法規網站取得地方自治法規。"""

    def __init__(
        self,
        output_dir: Path | None = None,
        city: str = "taipei",
        limit: int = DEFAULT_LOCAL_LIMIT,
        rate_limit: float = 2.0,
    ) -> None:
        super().__init__(
            output_dir=output_dir or Path("kb_data/regulations/local"),
            rate_limit=rate_limit,
        )
        self.city = city
        self.limit = limit
        self.base_url = LOCAL_LAW_URLS.get(city, "")

    def name(self) -> str:
        city_names = {"taipei": "臺北市"}
        return f"{city_names.get(self.city, self.city)}地方法規"

    def fetch(self) -> list[FetchResult]:
        """爬取地方法規列表頁並逐頁取全文。"""
        if not self.base_url:
            logger.error("不支援的城市代碼：%s", self.city)
            return []

        headers = {"User-Agent": _USER_AGENT}

        # 首頁有最新法規連結；/Law/LawSearch 是搜尋表單
        list_url = f"{self.base_url}/Law"
        try:
            resp = self._request_with_retry(
                "get", list_url, headers=headers, timeout=30,
            )
        except requests.RequestException as exc:
            logger.error("取得 %s 法規列表失敗：%s", self.city, exc)
            return []

        items = self._parse_list_page(resp.text)
        items = items[: self.limit]

        results: list[FetchResult] = []
        for idx, item in enumerate(items):
            title = item.get("title", f"地方法規_{idx + 1}")
            safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)[:60]
            detail_url = item.get("url", "")
            category = item.get("category", "")

            # 取全文
            full_text = ""
            if detail_url:
                try:
                    detail_resp = self._request_with_retry(
                        "get", detail_url, headers=headers, timeout=30,
                    )
                    full_text = self._extract_content(detail_resp.text)
                except requests.RequestException as exc:
                    logger.warning("取得地方法規全文失敗（%s）：%s", title, exc)

            source_url = detail_url or list_url

            body = f"# {title}\n\n"
            if category:
                body += f"**類別**：{category}\n\n"
            body += f"**地區**：{self.city}\n\n"
            if full_text:
                body += f"## 法規內容\n\n{full_text}\n\n"

            content_hash = self._compute_hash(body)
            metadata = {
                "title": title,
                "doc_type": "地方法規",
                "source": f"{self.city}法規查詢系統",
                "city": self.city,
                "category": category,
                "tags": ["地方法規", self.city],
                "source_level": SOURCE_LEVEL_A,
                "source_url": source_url,
                "content_hash": content_hash,
            }

            file_path = self.output_dir / f"local_{self.city}_{safe_title}.md"
            self._write_markdown(file_path, metadata, body)
            results.append(FetchResult(
                file_path=file_path,
                metadata=metadata,
                collection="regulations",
                source_level=SOURCE_LEVEL_A,
                source_url=source_url,
                content_hash=content_hash,
            ))

        logger.info("LocalRegulationFetcher 擷取完成：%d 個檔案", len(results))
        return results

    # ------------------------------------------------------------------
    # HTML 解析
    # ------------------------------------------------------------------

    def _parse_list_page(self, html: str) -> list[dict]:
        """從列表頁 HTML 提取法規項目。"""
        import html as html_mod

        items: list[dict] = []
        # 臺北市法規使用 /Law/LawSearch/LawInformation/{id} 格式
        pattern = re.compile(
            r'<a[^>]+href=["\']([^"\']*(?:LawInformation|LawArticleContent|LawContent|LawAll)[^"\']*)["\'][^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        for match in pattern.finditer(html):
            href = match.group(1).strip()
            title = html_mod.unescape(re.sub(r'<[^>]+>', '', match.group(2)).strip())
            if not title:
                continue

            if href.startswith("/"):
                href = f"{self.base_url}{href}"
            elif not href.startswith("http"):
                href = f"{self.base_url}/{href}"

            items.append({"title": title, "url": href})

        return items

    @staticmethod
    def _extract_content(html: str) -> str:
        """從法規詳情頁提取主要內容。"""
        content_match = re.search(
            r'<div[^>]*(?:id|class)=["\'][^"\']*(?:content|law-content|article)[^"\']*["\'][^>]*>(.*?)</div>',
            html, re.DOTALL | re.IGNORECASE,
        )
        if content_match:
            return html_to_markdown(content_match.group(1))

        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
        if body_match:
            return html_to_markdown(body_match.group(1))

        return html_to_markdown(html)
