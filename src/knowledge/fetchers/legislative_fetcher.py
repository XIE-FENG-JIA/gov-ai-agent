"""立法院議案 Fetcher — 從 g0v ly.govapi.tw 取得委員提案與法律案。"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import requests

from src.knowledge.fetchers.base import BaseFetcher, FetchResult
from src.knowledge.fetchers.constants import (
    DEFAULT_LY_LIMIT,
    DEFAULT_LY_TERM,
    LY_GOVAPI_URL,
    SOURCE_LEVEL_B,
)

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


class LegislativeFetcher(BaseFetcher):
    """從 g0v ly.govapi.tw /bills 端點擷取立法院議案。

    API: GET https://v2.ly.govapi.tw/bills?page=N&limit=M
    資料量：14 萬筆以上，含議案名稱、提案人、附件下載連結等。
    """

    def __init__(
        self,
        output_dir: Path | None = None,
        term: str = DEFAULT_LY_TERM,
        limit: int = DEFAULT_LY_LIMIT,
        rate_limit: float = 1.0,
    ) -> None:
        super().__init__(
            output_dir=output_dir or Path("kb_data/policies/legislative"),
            rate_limit=rate_limit,
        )
        self.term = term
        self.limit = limit

    def name(self) -> str:
        return "立法院議案"

    def fetch(self) -> list[FetchResult]:
        """從 g0v 立法院 API 取得議案清單。"""
        headers = {"User-Agent": _USER_AGENT}
        all_bills: list[dict] = []
        page = 1
        per_page = min(self.limit, 100)

        while len(all_bills) < self.limit:
            url = f"{LY_GOVAPI_URL}/bills"
            params: dict = {"page": page, "limit": per_page}

            # 篩選屆期（all 表示不篩選）
            if self.term and self.term != "all":
                params["屆"] = self.term

            data = self._fetch_json(
                "get", url, params=params, headers=headers, timeout=30,
            )
            if data is None:
                break

            bills = data.get("bills", [])
            if not bills:
                break

            all_bills.extend(bills)
            total_page = data.get("total_page", 1)
            if page >= total_page or len(all_bills) >= self.limit:
                break
            page += 1

        all_bills = all_bills[: self.limit]

        results: list[FetchResult] = []
        for bill in all_bills:
            bill_name = bill.get("議案名稱", "無標題")
            safe_name = re.sub(r'[<>:"/\\|?*]', "_", bill_name)[:60]
            term = str(bill.get("屆", ""))
            session = str(bill.get("會期", ""))
            proposer = bill.get("提案單位/提案委員", bill.get("提案人", ""))
            status = bill.get("議案狀態", "")
            bill.get("議案編號", "")
            category = bill.get("議案類別", "")
            meeting_desc = bill.get("會議代碼:str", "")
            latest_date = bill.get("最新進度日期", "")

            # 附件連結
            attachments = bill.get("相關附件", [])
            pdf_url = ""
            for att in attachments if isinstance(attachments, list) else []:
                if isinstance(att, dict) and "PDF" in att.get("名稱", ""):
                    pdf_url = att.get("網址", "")
                    break

            source_url = pdf_url or ""

            body = f"# {bill_name}\n\n"
            if term:
                body += f"**屆期**：第 {term} 屆\n\n"
            if session:
                body += f"**會期**：第 {session} 會期\n\n"
            if meeting_desc:
                body += f"**會議**：{meeting_desc}\n\n"
            if proposer:
                body += f"**提案人**：{proposer}\n\n"
            if category:
                body += f"**議案類別**：{category}\n\n"
            if status:
                body += f"**狀態**：{status}\n\n"
            if latest_date:
                body += f"**最新進度日期**：{latest_date}\n\n"

            content_hash = self._compute_hash(body)
            metadata = {
                "title": bill_name,
                "doc_type": "立法院議案",
                "source": "立法院開放資料（g0v）",
                "term": term,
                "session_period": session,
                "bill_proposer": proposer,
                "bill_status": status,
                "bill_category": category,
                "tags": ["立法院", "議案"],
                "source_level": SOURCE_LEVEL_B,
                "source_url": source_url,
                "content_hash": content_hash,
            }

            file_path = self.output_dir / f"legislative_{safe_name}.md"
            self._write_markdown(file_path, metadata, body)
            results.append(FetchResult(
                file_path=file_path,
                metadata=metadata,
                collection="policies",
                source_level=SOURCE_LEVEL_B,
                source_url=source_url,
                content_hash=content_hash,
            ))

        logger.info("LegislativeFetcher 擷取完成：%d 個檔案", len(results))
        return results
