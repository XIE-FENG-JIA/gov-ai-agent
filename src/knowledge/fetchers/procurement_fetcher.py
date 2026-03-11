"""政府採購公告 Fetcher — 從 g0v 社群 API 取得招標/決標公告。"""
from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path

import requests

from src.knowledge.fetchers.base import BaseFetcher, FetchResult
from src.knowledge.fetchers.constants import (
    DEFAULT_PCC_DAYS,
    DEFAULT_PCC_LIMIT,
    PCC_API_URL,
    SOURCE_LEVEL_B,
)

logger = logging.getLogger(__name__)


class ProcurementFetcher(BaseFetcher):
    """從 pcc-api.openfun.app（g0v 社群維護）擷取政府採購公告。

    API 端點：
    - /api/searchbytitle?query=xxx&page=N  — 依標案名稱搜尋
    - /api/listbydate?date=YYYYMMDD        — 依日期列出公告
    - /api/tender?unit_id=xxx&job_number=xxx — 單一標案詳情
    """

    def __init__(
        self,
        output_dir: Path | None = None,
        days: int = DEFAULT_PCC_DAYS,
        limit: int = DEFAULT_PCC_LIMIT,
        keyword: str = "",
        rate_limit: float = 1.0,
    ) -> None:
        super().__init__(
            output_dir=output_dir or Path("kb_data/policies/procurement"),
            rate_limit=rate_limit,
        )
        self.days = days
        self.limit = limit
        self.keyword = keyword

    def name(self) -> str:
        return "政府採購公告"

    def fetch(self) -> list[FetchResult]:
        """取得近期採購公告。

        若有指定 keyword 則用 searchbytitle，否則用 listbydate 取最近幾天。
        """
        if self.keyword:
            return self._fetch_by_keyword()
        return self._fetch_by_date()

    # ------------------------------------------------------------------
    # 策略一：依關鍵字搜尋
    # ------------------------------------------------------------------

    def _fetch_by_keyword(self) -> list[FetchResult]:
        all_records: list[dict] = []
        page = 1

        while len(all_records) < self.limit:
            url = f"{PCC_API_URL}/api/searchbytitle"
            params = {"query": self.keyword, "page": page}

            try:
                resp = self._request_with_retry("get", url, params=params, timeout=30)
            except requests.RequestException as exc:
                logger.error("查詢採購 API 失敗：%s", exc)
                break

            try:
                data = resp.json()
            except Exception as exc:
                logger.error("解析採購 JSON 失敗：%s", exc)
                break

            records = data.get("records", [])
            if not records:
                break

            all_records.extend(records)
            total_pages = data.get("total_pages", 1)
            if page >= total_pages or len(all_records) >= self.limit:
                break
            page += 1

        return self._records_to_results(all_records[: self.limit])

    # ------------------------------------------------------------------
    # 策略二：依日期列出
    # ------------------------------------------------------------------

    def _fetch_by_date(self) -> list[FetchResult]:
        all_records: list[dict] = []
        today = datetime.date.today()

        for offset in range(self.days):
            if len(all_records) >= self.limit:
                break
            target = today - datetime.timedelta(days=offset)
            date_str = target.strftime("%Y%m%d")
            url = f"{PCC_API_URL}/api/listbydate"
            params = {"date": date_str}

            try:
                resp = self._request_with_retry("get", url, params=params, timeout=30)
            except requests.RequestException as exc:
                logger.warning("取得 %s 採購公告失敗：%s", date_str, exc)
                continue

            try:
                data = resp.json()
            except Exception as exc:
                logger.warning("解析 %s 採購 JSON 失敗：%s", date_str, exc)
                continue

            records = data.get("records", [])
            all_records.extend(records)

        return self._records_to_results(all_records[: self.limit])

    # ------------------------------------------------------------------
    # 共用：records → FetchResult
    # ------------------------------------------------------------------

    def _records_to_results(self, records: list[dict]) -> list[FetchResult]:
        results: list[FetchResult] = []

        for rec in records:
            brief = rec.get("brief", {})
            if isinstance(brief, str):
                title = brief
                tender_type = ""
                category = ""
            else:
                title = brief.get("title", "無標題")
                tender_type = brief.get("type", "")
                category = brief.get("category", "")

            safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)[:60]
            unit_name = rec.get("unit_name", "") or ""
            date = rec.get("date", "")
            job_number = rec.get("job_number", "")
            rec.get("unit_id", "")
            rec.get("tender_api_url", "")
            source_url = rec.get("url", "")
            if source_url and not source_url.startswith("http"):
                source_url = f"{PCC_API_URL}{source_url}"

            body = f"# {title}\n\n"
            if unit_name:
                body += f"**機關名稱**：{unit_name}\n\n"
            if tender_type:
                body += f"**標案類型**：{tender_type}\n\n"
            if category:
                body += f"**分類**：{category}\n\n"
            if date:
                body += f"**公告日期**：{date}\n\n"
            if job_number:
                body += f"**標案案號**：{job_number}\n\n"

            content_hash = self._compute_hash(body)
            metadata = {
                "title": title,
                "doc_type": "採購公告",
                "source": "政府電子採購網（g0v）",
                "agency": unit_name,
                "date": str(date),
                "job_number": job_number,
                "tags": ["採購", "招標"],
                "source_level": SOURCE_LEVEL_B,
                "source_url": source_url,
                "content_hash": content_hash,
            }

            file_path = self.output_dir / f"procurement_{safe_title}.md"
            self._write_markdown(file_path, metadata, body)
            results.append(FetchResult(
                file_path=file_path,
                metadata=metadata,
                collection="policies",
                source_level=SOURCE_LEVEL_B,
                source_url=source_url,
                content_hash=content_hash,
            ))

        logger.info("ProcurementFetcher 擷取完成：%d 個檔案", len(results))
        return results
