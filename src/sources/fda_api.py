"""Adapter for Taiwan FDA public notice API payloads."""

from __future__ import annotations

import json
import hashlib
import time
from collections import deque
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urljoin

import requests

from src.core.models import PublicGovDoc
from src.knowledge.fetchers.base import html_to_markdown
from src.sources._common import build_headers, request_with_proxy_bypass, throttle, with_fixture_fallback
from src.sources.base import BaseSourceAdapter


class FdaApiAdapter(BaseSourceAdapter):
    """Adapter for public Taiwan FDA notice listings."""

    SOURCE_AGENCY = "衛生福利部食品藥物管理署"
    API_URL = "https://www.fda.gov.tw/DataAction"
    DEFAULT_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "fda_api" / "notices.json"

    def __init__(
        self,
        *,
        session: requests.sessions.Session | None = None,
        api_url: str = API_URL,
        query_params: dict[str, Any] | None = None,
        rate_limit: float = 2.0,
        timeout: float = 30.0,
        fixture_path: Path | None = None,
    ) -> None:
        self.session = session or requests.Session()
        self.api_url = api_url
        self.query_params = query_params or {}
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.fixture_path = fixture_path if fixture_path is not None else self.DEFAULT_FIXTURE_PATH
        self._last_request_time = 0.0
        self._notice_cache: dict[str, dict[str, Any]] = {}

    def list(self, since_date: date | None = None, limit: int = 3) -> Iterable[dict[str, Any]]:
        if limit <= 0:
            return []

        docs: list[dict[str, Any]] = []
        for raw in self._load_catalog(limit=max(limit, 3)):
            source_date = self._extract_source_date(raw)
            if since_date is not None and source_date is not None and source_date < since_date:
                continue

            notice_id = self._extract_notice_id(raw)
            title = self._extract_title(raw)
            if not notice_id or not title:
                continue

            docs.append({"id": notice_id, "title": title, "date": source_date})
            if len(docs) == limit:
                break
        return docs

    def fetch(self, doc_id: str) -> dict[str, Any]:
        normalized_id = doc_id.strip()
        if not normalized_id:
            raise ValueError("doc_id must not be blank")
        if normalized_id not in self._notice_cache:
            self._load_catalog(limit=50, force_refresh=True)
        if normalized_id not in self._notice_cache:
            raise KeyError(f"FDA notice not found: {normalized_id}")
        return self._notice_cache[normalized_id]

    def normalize(self, raw: dict[str, Any]) -> PublicGovDoc:
        notice_id = self._extract_notice_id(raw)
        title = self._extract_title(raw)
        source_url = self._extract_source_url(raw)
        if not notice_id or not title or not source_url:
            raise ValueError("raw FDA payload is missing id/title/url")

        agency_name = self._extract_first_text(raw, "Agency", "agency", "OrgName", "dept", "Department")
        return PublicGovDoc(
            source_id=notice_id,
            source_url=source_url,
            source_agency=agency_name or self.SOURCE_AGENCY,
            source_doc_no=self._extract_first_text(raw, "DocNo", "doc_no", "No", "NoticeNo", "SerialNo") or notice_id,
            source_date=self._extract_source_date(raw),
            doc_type=self._extract_first_text(raw, "Category", "category", "Type", "type_name") or "公告",
            raw_snapshot_path=None,
            crawl_date=date.today(),
            content_md=self._build_content_markdown(raw),
            synthetic=bool(raw.get("_fixture_fallback")),
            fixture_fallback=bool(raw.get("_fixture_fallback")),
        )

    def _load_catalog(self, *, limit: int, force_refresh: bool = False) -> list[dict[str, Any]]:
        if self._notice_cache and not force_refresh and len(self._notice_cache) >= limit:
            return list(self._notice_cache.values())

        result = with_fixture_fallback(
            lambda: self._decode_payload(self._request_json()),
            self._load_fixture_payload,
            handled_exceptions=(requests.RequestException, ValueError, TypeError),
        )
        notices = self._extract_items(result.value)
        self._notice_cache = {
            notice_id: {
                **notice,
                "_fixture_fallback": result.used_fixture,
            }
            for notice in notices
            if isinstance(notice, dict)
            for notice_id in [self._extract_notice_id(notice)]
            if notice_id
        }
        return list(self._notice_cache.values())

    def _request_json(self) -> requests.Response:
        self._throttle()
        response = request_with_proxy_bypass(
            self.session,
            "get",
            self.api_url,
            allow_ssl_fallback=True,
            params=self.query_params or None,
            headers=build_headers(accept="application/json, text/plain, */*"),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response

    def _load_fixture_payload(self, exc: Exception) -> Any:
        if not self.fixture_path.exists():
            raise exc
        return json.loads(self.fixture_path.read_text(encoding="utf-8"))

    def _throttle(self) -> None:
        self._last_request_time = throttle(self._last_request_time, self.rate_limit)

    @staticmethod
    def _decode_payload(response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return json.loads(response.text)

    @classmethod
    def _extract_items(cls, payload: Any) -> list[dict[str, Any]]:
        queue: deque[Any] = deque([payload])
        while queue:
            node = queue.popleft()
            if isinstance(node, list):
                dict_items = [item for item in node if isinstance(item, dict)]
                if dict_items:
                    return dict_items
                queue.extend(node)
                continue
            if isinstance(node, dict):
                for key in ("items", "Item", "Rows", "rows", "data", "Data", "result", "Result", "payload", "d", "list"):
                    if key in node:
                        queue.append(node[key])
                queue.extend(value for value in node.values() if isinstance(value, (dict, list)))
        return []

    @classmethod
    def _extract_notice_id(cls, raw: dict[str, Any]) -> str:
        explicit_id = cls._extract_first_text(
            raw,
            "Id",
            "ID",
            "NoticeID",
            "notice_id",
            "Pk",
            "Seq",
            "SerialNo",
            "No",
        )
        if explicit_id:
            return explicit_id

        title = cls._extract_title(raw)
        source_date = cls._extract_source_date(raw)
        if not title:
            return ""

        seed = f"{source_date.isoformat() if source_date else 'unknown'}|{title}".encode("utf-8")
        digest = hashlib.sha1(seed).hexdigest()[:10]
        date_prefix = source_date.strftime("%Y%m%d") if source_date else "unknown"
        return f"FDA-{date_prefix}-{digest}"

    @classmethod
    def _extract_title(cls, raw: dict[str, Any]) -> str:
        return cls._extract_first_text(raw, "Title", "title", "Subject", "subject", "Name", "name", "標題", "主旨")

    @classmethod
    def _extract_source_url(cls, raw: dict[str, Any]) -> str:
        value = cls._extract_first_text(raw, "Link", "link", "Url", "url", "DetailUrl", "detail_url", "Href", "href")
        if not value:
            query: dict[str, str] = {}
            title = cls._extract_title(raw)
            source_date = cls._extract_source_date(raw)
            if title:
                query["keyword"] = title
            if source_date is not None:
                query_date = source_date.strftime("%Y/%m/%d")
                query["startdate"] = query_date
                query["enddate"] = query_date
            return f"{cls.API_URL}?{urlencode(query)}" if query else cls.API_URL
        return urljoin(cls.API_URL, value)

    @classmethod
    def _extract_source_date(cls, raw: dict[str, Any]) -> date | None:
        for key in (
            "PublishDate",
            "publish_date",
            "PostDate",
            "post_date",
            "UpdateDate",
            "update_date",
            "Date",
            "date",
            "ModifyDate",
            "modify_date",
            "公告日期",
            "發布日期",
        ):
            value = raw.get(key)
            if not value:
                continue
            text = str(value).strip().replace("/", "-")
            for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return datetime.strptime(text[:19], fmt).date()
                except ValueError:
                    continue
            try:
                return date.fromisoformat(text[:10])
            except ValueError:
                continue
        return None

    @classmethod
    def _build_content_markdown(cls, raw: dict[str, Any]) -> str:
        title = cls._extract_title(raw)
        source_url = cls._extract_source_url(raw)
        published_at = cls._extract_source_date(raw)
        summary = cls._extract_first_text(
            raw,
            "Summary",
            "summary",
            "Description",
            "description",
            "Content",
            "content",
            "內容",
        )
        category = cls._extract_first_text(raw, "Category", "category", "Type", "type_name")
        doc_no = cls._extract_first_text(raw, "DocNo", "doc_no", "No", "NoticeNo", "SerialNo")
        attachment_url = cls._extract_first_text(raw, "附檔連結")

        lines = [f"# {title}"]
        if published_at is not None:
            lines.append(f"**發布日期**：{published_at.isoformat()}")
        if category:
            lines.append(f"**類別**：{category}")
        if doc_no:
            lines.append(f"**公告編號**：{doc_no}")
        if source_url:
            lines.append(f"**原文連結**：{source_url}")
        if attachment_url:
            lines.append(f"**附檔連結**：{attachment_url.rstrip(',')}")
        if summary:
            lines.append(f"## 摘要\n{html_to_markdown(summary)}")
        return "\n\n".join(lines)

    @staticmethod
    def _extract_first_text(raw: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = raw.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return ""
