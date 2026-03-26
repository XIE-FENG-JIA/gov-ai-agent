"""監察院糾正案 Fetcher — 爬取監察院糾正案與調查報告。"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import requests

from src.knowledge.fetchers.base import BaseFetcher, FetchResult, html_to_markdown
from src.knowledge.fetchers.constants import (
    CONTROLYUAN_BASE_URL,
    CONTROLYUAN_CORRECTION_URL,
    DEFAULT_CONTROLYUAN_LIMIT,
    SOURCE_LEVEL_A,
)

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


class ControlYuanFetcher(BaseFetcher):
    """爬取監察院糾正案文與調查報告摘要。"""

    def __init__(
        self,
        output_dir: Path | None = None,
        limit: int = DEFAULT_CONTROLYUAN_LIMIT,
        rate_limit: float = 2.0,
    ) -> None:
        super().__init__(
            output_dir=output_dir or Path("kb_data/policies/control_yuan"),
            rate_limit=rate_limit,
        )
        self.limit = limit

    def name(self) -> str:
        return "監察院糾正案"

    def fetch(self) -> list[FetchResult]:
        """爬取監察院糾正案列表頁，再逐頁取摘要。"""
        headers = {"User-Agent": _USER_AGENT}

        try:
            resp = self._request_with_retry(
                "get", CONTROLYUAN_CORRECTION_URL, headers=headers, timeout=30,
            )
        except requests.RequestException as exc:
            logger.error("取得監察院糾正案列表失敗：%s", exc)
            return []

        items = self._parse_list_page(resp.text)
        items = items[: self.limit]

        results: list[FetchResult] = []
        for idx, item in enumerate(items):
            title = item.get("title", f"糾正案_{idx + 1}")
            safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)[:60]
            detail_url = item.get("url", "")
            date = item.get("date", "")
            agency = item.get("agency", "")

            # 取摘要
            summary = ""
            if detail_url:
                try:
                    detail_resp = self._request_with_retry(
                        "get", detail_url, headers=headers, timeout=30,
                    )
                    summary = self._extract_content(detail_resp.text)
                except requests.RequestException as exc:
                    logger.warning("取得糾正案摘要失敗（%s）：%s", title, exc)

            source_url = detail_url or CONTROLYUAN_CORRECTION_URL

            body = f"# {title}\n\n"
            if agency:
                body += f"**被糾正機關**：{agency}\n\n"
            if date:
                body += f"**糾正日期**：{date}\n\n"
            if summary:
                body += f"## 糾正案摘要\n\n{summary}\n\n"

            content_hash = self._compute_hash(body)
            metadata = {
                "title": title,
                "doc_type": "糾正案",
                "source": "監察院",
                "agency": agency,
                "date": date,
                "tags": ["監察院", "糾正案"],
                "source_level": SOURCE_LEVEL_A,
                "source_url": source_url,
                "content_hash": content_hash,
            }

            file_path = self.output_dir / f"controlyuan_{safe_title}.md"
            if self._write_markdown(file_path, metadata, body) is not None:
                results.append(FetchResult(
                    file_path=file_path,
                    metadata=metadata,
                    collection="policies",
                    source_level=SOURCE_LEVEL_A,
                    source_url=source_url,
                    content_hash=content_hash,
                ))

        logger.info("ControlYuanFetcher 擷取完成：%d 個檔案", len(results))
        return results

    # ------------------------------------------------------------------
    # HTML 解析
    # ------------------------------------------------------------------

    def _parse_list_page(self, html: str) -> list[dict]:
        """從糾正案列表頁 HTML 提取項目。"""
        items: list[dict] = []

        # 監察院列表通常以 <a> 連結呈現
        pattern = re.compile(
            r'<a[^>]+href=["\']([^"\']*CyBsBoxContent[^"\']*)["\'][^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        for match in pattern.finditer(html):
            href = match.group(1).strip()
            title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
            if not title:
                continue

            if href.startswith("/"):
                href = f"{CONTROLYUAN_BASE_URL}{href}"
            elif not href.startswith("http"):
                href = f"{CONTROLYUAN_BASE_URL}/{href}"

            # 嘗試提取日期
            date_match = re.search(r'(\d{2,4}[./\-]\d{1,2}[./\-]\d{1,2})', title)
            date = date_match.group(1) if date_match else ""

            items.append({
                "title": title,
                "url": href,
                "date": date,
            })

        return items

    @staticmethod
    def _extract_content(html: str) -> str:
        """從糾正案詳情頁提取主要內容。"""
        content_match = re.search(
            r'<div[^>]*(?:id|class)=["\'][^"\']*(?:content|main|article)[^"\']*["\'][^>]*>(.*?)</div>',
            html, re.DOTALL | re.IGNORECASE,
        )
        if content_match:
            return html_to_markdown(content_match.group(1))

        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
        if body_match:
            return html_to_markdown(body_match.group(1))

        return html_to_markdown(html)
