"""立法院質詢/會議 Fetcher — 從 g0v 社群 API 取得質詢與會議紀錄。"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import requests

from src.knowledge.fetchers.base import BaseFetcher, FetchResult
from src.knowledge.fetchers.constants import (
    DEFAULT_LY_LIMIT,
    LY_GOVAPI_URL,
    SOURCE_LEVEL_B,
)

logger = logging.getLogger(__name__)


class LegislativeDebateFetcher(BaseFetcher):
    """從 ly.govapi.tw（g0v 社群維護）擷取立法院質詢與會議紀錄。"""

    def __init__(
        self,
        output_dir: Path | None = None,
        limit: int = DEFAULT_LY_LIMIT,
        rate_limit: float = 1.0,
    ) -> None:
        super().__init__(
            output_dir=output_dir or Path("kb_data/policies/legislative_debates"),
            rate_limit=rate_limit,
        )
        self.limit = limit

    def name(self) -> str:
        return "立法院質詢/會議"

    def fetch(self) -> list[FetchResult]:
        """從 g0v ly.govapi.tw 取得質詢紀錄。

        API: GET https://v2.ly.govapi.tw/interpellations
        """
        all_items: list[dict] = []
        page = 1
        page_size = min(self.limit, 50)

        while len(all_items) < self.limit:
            url = f"{LY_GOVAPI_URL}/interpellations"
            params = {"page": page, "limit": page_size}

            try:
                resp = self._request_with_retry(
                    "get", url, params=params, timeout=30,
                )
            except requests.RequestException as exc:
                logger.error("查詢 ly.govapi.tw 失敗：%s", exc)
                break

            try:
                data = resp.json()
            except Exception as exc:
                logger.error("解析 ly.govapi.tw JSON 失敗：%s", exc)
                break

            # API 回傳格式：{"interpellations": [...], "total_page": N, ...}
            if isinstance(data, dict):
                items = data.get("interpellations", data.get("data", data.get("results", [])))
                total_page = int(data.get("total_page", 1))
            else:
                items = data
                total_page = 1
            if not items:
                break

            all_items.extend(items)
            if page >= total_page or len(all_items) >= self.limit:
                break
            page += 1

        all_items = all_items[: self.limit]

        results: list[FetchResult] = []
        for idx, item in enumerate(all_items):
            # API 欄位使用中文 key
            title = item.get("事由", item.get("title", f"質詢紀錄_{idx + 1}"))
            safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)[:60]
            legislators = item.get("質詢委員", item.get("legislator", []))
            legislator = ", ".join(legislators) if isinstance(legislators, list) else str(legislators)
            date = item.get("刊登日期", item.get("date", ""))
            content = item.get("說明", item.get("content", ""))
            item.get("屆", "")
            item.get("會期", "")
            meeting_desc = item.get("會議代碼:str", "")
            source_url = item.get("url", "")

            body = f"# {title}\n\n"
            if legislator:
                body += f"**質詢委員**：{legislator}\n\n"
            if meeting_desc:
                body += f"**會議**：{meeting_desc}\n\n"
            if date:
                body += f"**日期**：{date}\n\n"
            if content:
                body += f"## 說明\n\n{content}\n\n"

            content_hash = self._compute_hash(body)
            metadata = {
                "title": title,
                "doc_type": "立法院質詢",
                "source": "立法院 g0v API",
                "legislator": legislator,
                "date": date,
                "tags": ["立法院", "質詢"],
                "source_level": SOURCE_LEVEL_B,
                "source_url": source_url,
                "content_hash": content_hash,
            }

            file_path = self.output_dir / f"debate_{safe_title}.md"
            self._write_markdown(file_path, metadata, body)
            results.append(FetchResult(
                file_path=file_path,
                metadata=metadata,
                collection="policies",
                source_level=SOURCE_LEVEL_B,
                source_url=source_url,
                content_hash=content_hash,
            ))

        logger.info("LegislativeDebateFetcher 擷取完成：%d 個檔案", len(results))
        return results
