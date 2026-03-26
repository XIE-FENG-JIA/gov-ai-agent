"""考試院人事法規 Fetcher — 從考試院 Open Data JSON 取得法規全文。"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import requests

from src.knowledge.fetchers.base import BaseFetcher, FetchResult, html_to_markdown
from src.knowledge.fetchers.constants import (
    DEFAULT_EXAMYUAN_LIMIT,
    EXAMYUAN_BASE_URL,
    SOURCE_LEVEL_B,
)

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# Open Data JSON 端點（考試院提供各類法規的 JSON 下載）
_OPENDATA_PAGE = f"{EXAMYUAN_BASE_URL}/OpenDataWeb.aspx"


class ExamYuanFetcher(BaseFetcher):
    """從考試院 Open Data JSON 下載法規全文。"""

    def __init__(
        self,
        output_dir: Path | None = None,
        limit: int = DEFAULT_EXAMYUAN_LIMIT,
        rate_limit: float = 2.0,
    ) -> None:
        super().__init__(
            output_dir=output_dir or Path("kb_data/regulations/exam_yuan"),
            rate_limit=rate_limit,
        )
        self.limit = limit

    def name(self) -> str:
        return "考試院人事法規"

    def fetch(self) -> list[FetchResult]:
        """先從 Open Data 頁面找 JSON 下載連結，再逐一下載法規。"""
        headers = {"User-Agent": _USER_AGENT}

        # 取 Open Data 頁面，找 JSON 下載連結
        json_urls = self._discover_json_urls(headers)
        if not json_urls:
            logger.warning("未找到考試院 Open Data JSON 連結，改用類別列表")
            return self._fetch_from_category(headers)

        results: list[FetchResult] = []
        for url in json_urls:
            if len(results) >= self.limit:
                break
            try:
                resp = self._request_with_retry("get", url, headers=headers, timeout=30)
            except requests.RequestException as exc:
                logger.warning("下載考試院 JSON 失敗（%s）：%s", url, exc)
                continue

            items = self._parse_json_text(resp.text)
            for item in items:
                if len(results) >= self.limit:
                    break
                result = self._item_to_result(item)
                if result:
                    results.append(result)

        logger.info("ExamYuanFetcher 擷取完成：%d 個檔案", len(results))
        return results

    def _discover_json_urls(self, headers: dict) -> list[str]:
        """從 Open Data 頁面找出所有 .json 下載連結。"""
        try:
            resp = self._request_with_retry("get", _OPENDATA_PAGE, headers=headers, timeout=15)
        except requests.RequestException:
            return []

        urls = re.findall(
            r'href=["\']([^"\']*\.json)["\']',
            resp.text, re.IGNORECASE,
        )
        # 只取法規相關 JSON（排除行政函釋等較雜的）
        return list(dict.fromkeys(urls))  # 去重保序

    @staticmethod
    def _parse_json_text(text: str) -> list[dict]:
        """解析考試院 Open Data JSON（可能是多筆 JSON 物件串接）。"""
        import json

        # 先嘗試標準 JSON
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                if "法規名稱" in data:
                    return [data]
                for key in ("Laws", "data", "records"):
                    if key in data and isinstance(data[key], list):
                        return data[key]
                return [data]
        except json.JSONDecodeError:
            pass

        # 串接 JSON：逐一解析 {...}{...}
        items: list[dict] = []
        decoder = json.JSONDecoder()
        pos = 0
        while pos < len(text):
            # 找下一個 { 開頭
            next_brace = text.find("{", pos)
            if next_brace == -1:
                break
            try:
                obj, end_idx = decoder.raw_decode(text, next_brace)
                if isinstance(obj, dict):
                    items.append(obj)
                pos = end_idx
            except json.JSONDecodeError:
                pos = next_brace + 1

        return items

    def _item_to_result(self, item: dict) -> FetchResult | None:
        """將單一法規 dict 轉為 FetchResult。"""
        title = item.get("法規名稱", item.get("LawName", ""))
        if not title:
            return None

        safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)[:60]
        category = item.get("法規類別", "")
        law_system = item.get("法規體系", "")
        pub_date = item.get("訂定公發布日", "")
        update_date = item.get("最新異動日期", "")
        content_text = item.get("法規內容", "")
        source_url = item.get("資料網址", "")

        body = f"# {title}\n\n"
        if category:
            body += f"**法規類別**：{category}\n\n"
        if law_system:
            body += f"**法規體系**：{law_system}\n\n"
        if pub_date:
            body += f"**訂定日期**：{pub_date}\n\n"
        if update_date:
            body += f"**最新異動**：{update_date}\n\n"
        if content_text:
            body += f"## 法規內容\n\n{content_text}\n\n"

        content_hash = self._compute_hash(body)
        metadata = {
            "title": title,
            "doc_type": "考試院法規",
            "source": "考試院法規資料庫",
            "category": category,
            "law_system": law_system,
            "tags": ["考試院", "人事法規"],
            "source_level": SOURCE_LEVEL_B,
            "source_url": source_url,
            "content_hash": content_hash,
        }

        file_path = self.output_dir / f"examyuan_{safe_title}.md"
        if self._write_markdown(file_path, metadata, body) is None:
            return None
        return FetchResult(
            file_path=file_path,
            metadata=metadata,
            collection="regulations",
            source_level=SOURCE_LEVEL_B,
            source_url=source_url,
            content_hash=content_hash,
        )

    def _fetch_from_category(self, headers: dict) -> list[FetchResult]:
        """備用方案：從類別列表頁爬取。"""
        list_url = f"{EXAMYUAN_BASE_URL}/LawCategoryContentList.aspx?CategoryID=110&size=30&page=1"
        try:
            resp = self._request_with_retry("get", list_url, headers=headers, timeout=30)
        except requests.RequestException as exc:
            logger.error("取得考試院法規列表失敗：%s", exc)
            return []

        items = self._parse_list_page(resp.text)
        items = items[: self.limit]

        results: list[FetchResult] = []
        for idx, item in enumerate(items):
            title = item.get("title", f"考試院法規_{idx + 1}")
            safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)[:60]
            detail_url = item.get("url", "")

            full_text = ""
            if detail_url:
                try:
                    detail_resp = self._request_with_retry(
                        "get", detail_url, headers=headers, timeout=30,
                    )
                    full_text = self._extract_content(detail_resp.text)
                except requests.RequestException as exc:
                    logger.warning("取得考試院法規全文失敗（%s）：%s", title, exc)

            source_url = detail_url or list_url
            body = f"# {title}\n\n"
            if full_text:
                body += f"## 法規內容\n\n{full_text}\n\n"

            content_hash = self._compute_hash(body)
            metadata = {
                "title": title,
                "doc_type": "考試院法規",
                "source": "考試院法規資料庫",
                "tags": ["考試院", "人事法規"],
                "source_level": SOURCE_LEVEL_B,
                "source_url": source_url,
                "content_hash": content_hash,
            }

            file_path = self.output_dir / f"examyuan_{safe_title}.md"
            if self._write_markdown(file_path, metadata, body) is not None:
                results.append(FetchResult(
                    file_path=file_path,
                    metadata=metadata,
                    collection="regulations",
                    source_level=SOURCE_LEVEL_B,
                    source_url=source_url,
                    content_hash=content_hash,
                ))

        return results

    @staticmethod
    def _parse_list_page(html: str) -> list[dict]:
        """從類別列表頁提取法規項目。"""
        items: list[dict] = []
        pattern = re.compile(
            r'<a[^>]+href=["\']([^"\']*LawContent[^"\']*)["\'][^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        for match in pattern.finditer(html):
            href = match.group(1).strip()
            title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
            if not title:
                continue
            if href.startswith("/"):
                href = f"{EXAMYUAN_BASE_URL}{href}"
            elif not href.startswith("http"):
                href = f"{EXAMYUAN_BASE_URL}/{href}"
            items.append({"title": title, "url": href})
        return items

    @staticmethod
    def _extract_content(html: str) -> str:
        """從法規詳情頁提取主要內容。"""
        for pattern in [
            r'<div[^>]*class=["\'][^"\']*law-content[^"\']*["\'][^>]*>(.*?)</div>',
            r'<div[^>]*id=["\']content["\'][^>]*>(.*?)</div>',
        ]:
            match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
            if match:
                return html_to_markdown(match.group(1))
        return ""
