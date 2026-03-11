"""政府資料開放平臺 Fetcher — 搜尋並保存資料集 metadata。

2026-03 更新：v2 REST API 已改為需要 API Key，改用前端搜尋端點
POST /api/front/dataset/list（免 API Key）。
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import requests

from src.knowledge.fetchers.base import BaseFetcher, FetchResult
from src.knowledge.fetchers.constants import (
    DEFAULT_OPENDATA_KEYWORD,
    DEFAULT_OPENDATA_LIMIT,
    OPENDATA_DETAIL_URL,
    SOURCE_LEVEL_B,
)

logger = logging.getLogger(__name__)

# 前端搜尋 API（免 API Key）
_FRONT_SEARCH_URL = "https://data.gov.tw/api/front/dataset/list"


class OpenDataFetcher(BaseFetcher):
    """從政府資料開放平臺搜尋資料集並儲存描述性 metadata。"""

    def __init__(
        self,
        output_dir: Path | None = None,
        keyword: str = DEFAULT_OPENDATA_KEYWORD,
        limit: int = DEFAULT_OPENDATA_LIMIT,
        rate_limit: float = 1.0,
    ) -> None:
        super().__init__(
            output_dir=output_dir or Path("kb_data/policies/opendata"),
            rate_limit=rate_limit,
        )
        self.keyword = keyword
        self.limit = limit

    def name(self) -> str:
        return "政府資料開放平臺"

    def fetch(self) -> list[FetchResult]:
        """搜尋關鍵字取得資料集清單，僅保存 metadata。

        使用前端 API POST /api/front/dataset/list，
        支援分頁，每頁最多 50 筆。
        """
        all_datasets: list[dict] = []
        page = 1
        page_size = min(self.limit, 50)

        while len(all_datasets) < self.limit:
            payload = {
                "bool": [{"fulltext": {"value": self.keyword}}],
                "filter": [],
                "page_num": page,
                "page_limit": page_size,
                "tids": [],
                "sort": "_score_desc",
            }

            try:
                resp = self._request_with_retry(
                    "post", _FRONT_SEARCH_URL,
                    json=payload, timeout=30,
                    headers={"Content-Type": "application/json"},
                )
            except requests.RequestException as exc:
                logger.error("查詢開放資料平臺失敗（已重試）：%s", exc)
                break

            try:
                data = resp.json()
            except Exception as exc:
                logger.error("解析開放資料 JSON 失敗：%s", exc)
                break

            if not isinstance(data, dict):
                logger.error("開放資料 API 回傳非預期格式：%s", type(data).__name__)
                break

            if not data.get("success"):
                err = data.get("error", data.get("message", "未知錯誤"))
                logger.error("開放資料 API 回傳錯誤：%s", err)
                break

            payload_data = data.get("payload", {})
            datasets = payload_data.get("search_result", [])
            if not datasets:
                break

            all_datasets.extend(datasets)
            total = payload_data.get("search_count", 0)
            if len(all_datasets) >= total or len(all_datasets) >= self.limit:
                break

            page += 1

        # 截斷至 limit
        all_datasets = all_datasets[:self.limit]

        results: list[FetchResult] = []
        for ds in all_datasets:
            dataset_id = str(ds.get("nid", ds.get("datasetId", "unknown")))
            title = ds.get("title", "無標題")
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:50]
            description = ds.get("content", ds.get("description", ""))
            agency = ds.get("agency_name", "")

            source_url = OPENDATA_DETAIL_URL.format(dataset_id=dataset_id)
            metadata = {
                "title": title,
                "doc_type": "開放資料",
                "source": "政府資料開放平臺",
                "agency": agency,
                "dataset_id": dataset_id,
                "tags": ["開放資料", self.keyword],
                "source_level": SOURCE_LEVEL_B,
                "source_url": source_url,
            }

            body = f"# {title}\n\n"
            if agency:
                body += f"**提供機關**：{agency}\n\n"
            if description:
                body += f"## 說明\n\n{description}\n\n"

            # 附加更多有用的 metadata
            category = ds.get("category_name", "")
            topic = ds.get("topic_name", "")
            update_freq = ds.get("updatefreq_desc", "")
            if category:
                body += f"**服務分類**：{category}\n\n"
            if topic:
                body += f"**主題**：{topic}\n\n"
            if update_freq:
                body += f"**更新頻率**：{update_freq}\n\n"

            content_hash = self._compute_hash(body)
            metadata["content_hash"] = content_hash

            file_path = self.output_dir / f"opendata_{dataset_id}_{safe_title}.md"
            self._write_markdown(file_path, metadata, body)
            results.append(FetchResult(
                file_path=file_path,
                metadata=metadata,
                collection="policies",
                source_level=SOURCE_LEVEL_B,
                source_url=source_url,
                content_hash=content_hash,
            ))

        logger.info("OpenDataFetcher 擷取完成：%d 個檔案", len(results))
        return results
