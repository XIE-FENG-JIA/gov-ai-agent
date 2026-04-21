"""Adapter for official government procurement notices on web.pcc.gov.tw."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

from src.core.models import PublicGovDoc
from src.knowledge.fetchers.base import html_to_markdown
from src.sources._common import build_headers, request_with_proxy_bypass, throttle, with_fixture_fallback
from src.sources.base import BaseSourceAdapter


class PccAdapter(BaseSourceAdapter):
    """Adapter for public tender notices published on the official PCC website."""

    SOURCE_AGENCY = "政府電子採購網"
    SEARCH_URL = "https://web.pcc.gov.tw/prkms/tender/common/basic/searchTenderBasic"
    DEFAULT_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "pcc"

    def __init__(
        self,
        *,
        session: requests.sessions.Session | None = None,
        search_url: str = SEARCH_URL,
        rate_limit: float = 2.0,
        timeout: float = 30.0,
        fixture_dir: Path | None = None,
    ) -> None:
        self.session = session or requests.Session()
        self.search_url = search_url
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.fixture_dir = fixture_dir if fixture_dir is not None else self.DEFAULT_FIXTURE_DIR
        self._last_request_time = 0.0
        self._summary_cache: dict[str, dict[str, Any]] = {}
        self._detail_cache: dict[str, dict[str, Any]] = {}

    def list(self, since_date: date | None = None, limit: int = 3) -> Iterable[dict[str, Any]]:
        if limit <= 0:
            return []

        docs: list[dict[str, Any]] = []
        for raw in self._load_catalog(limit=max(limit, 3)):
            source_date = raw.get("source_date")
            if since_date is not None and source_date is not None and source_date < since_date:
                continue

            docs.append({"id": raw["id"], "title": raw["title"], "date": source_date})
            if len(docs) == limit:
                break
        return docs

    def fetch(self, doc_id: str) -> dict[str, Any]:
        normalized_id = doc_id.strip()
        if not normalized_id:
            raise ValueError("doc_id must not be blank")
        if normalized_id in self._detail_cache:
            return self._detail_cache[normalized_id]
        if normalized_id not in self._summary_cache:
            self._load_catalog(limit=50, force_refresh=True)
        if normalized_id not in self._summary_cache:
            raise KeyError(f"PCC tender notice not found: {normalized_id}")

        summary = self._summary_cache[normalized_id]
        result = with_fixture_fallback(
            lambda: self._parse_detail_html(
                self._request_html(summary["detail_url"]).text,
                summary=summary,
            ),
            lambda exc: self._load_fixture_detail(normalized_id, summary=summary, exc=exc),
            handled_exceptions=(requests.RequestException, ValueError, TypeError),
        )
        detail = {
            **result.value,
            "_fixture_fallback": bool(summary.get("_fixture_fallback")) or result.used_fixture,
        }
        self._detail_cache[normalized_id] = detail
        return detail

    def normalize(self, raw: dict[str, Any]) -> PublicGovDoc:
        source_id = str(raw.get("id", "")).strip()
        title = str(raw.get("title", "")).strip()
        source_url = str(raw.get("source_url", raw.get("detail_url", ""))).strip()
        if not source_id or not title or not source_url:
            raise ValueError("raw PCC payload is missing id/title/url")

        return PublicGovDoc(
            source_id=source_id,
            source_url=source_url,
            source_agency=str(raw.get("agency", "")).strip() or self.SOURCE_AGENCY,
            source_doc_no=str(raw.get("tender_no", "")).strip() or source_id,
            source_date=raw.get("source_date"),
            doc_type="採購公告",
            raw_snapshot_path=None,
            crawl_date=date.today(),
            content_md=self._build_content_markdown(raw),
            synthetic=bool(raw.get("_fixture_fallback")),
            fixture_fallback=bool(raw.get("_fixture_fallback")),
        )

    def _load_catalog(self, *, limit: int, force_refresh: bool = False) -> list[dict[str, Any]]:
        if self._summary_cache and not force_refresh and len(self._summary_cache) >= limit:
            return list(self._summary_cache.values())

        result = with_fixture_fallback(
            lambda: self._parse_search_html(self._request_html(self.search_url).text),
            self._load_fixture_search,
            handled_exceptions=(requests.RequestException, ValueError, TypeError),
        )
        self._summary_cache = {
            entry["id"]: {
                **entry,
                "_fixture_fallback": result.used_fixture,
            }
            for entry in result.value
        }
        return list(self._summary_cache.values())[:limit]

    def _request_html(self, url: str) -> requests.Response:
        self._throttle()
        response = request_with_proxy_bypass(
            self.session,
            "get",
            url,
            headers=build_headers(accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
            timeout=self.timeout,
        )
        response.raise_for_status()
        response.encoding = response.encoding or "utf-8"
        return response

    def _load_fixture_search(self, exc: Exception) -> list[dict[str, Any]]:
        path = self.fixture_dir / "search.html"
        if not path.exists():
            raise exc
        return self._parse_search_html(path.read_text(encoding="utf-8"))

    def _load_fixture_detail(self, doc_id: str, *, summary: dict[str, Any], exc: Exception) -> dict[str, Any]:
        path = self.fixture_dir / f"{doc_id}.html"
        if not path.exists():
            raise exc
        return self._parse_detail_html(path.read_text(encoding="utf-8"), summary=summary)

    def _throttle(self) -> None:
        self._last_request_time = throttle(self._last_request_time, self.rate_limit)

    def _parse_search_html(self, html: str) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for match in re.finditer(r'<tr[^>]*data-id="(?P<id>[^"]+)"[^>]*>(?P<body>.*?)</tr>', html, re.IGNORECASE | re.DOTALL):
            body = match.group("body")
            doc_id = match.group("id").strip()
            title = self._extract_field(body, "title")
            detail_url = self._extract_href(body, "title")
            if not doc_id or not title or not detail_url:
                continue
            entries.append(
                {
                    "id": doc_id,
                    "title": title,
                    "detail_url": urljoin(self.search_url, detail_url),
                    "source_url": urljoin(self.search_url, detail_url),
                    "agency": self._extract_field(body, "agency") or self.SOURCE_AGENCY,
                    "tender_no": self._extract_field(body, "tender-no"),
                    "source_date": self._parse_date(self._extract_field(body, "date")),
                    "procurement_type": self._extract_field(body, "procurement-type"),
                    "summary": self._extract_field(body, "summary"),
                }
            )
        if not entries:
            raise ValueError("PCC search HTML did not contain any tender rows")
        return entries

    def _parse_detail_html(self, html: str, *, summary: dict[str, Any]) -> dict[str, Any]:
        content_html = self._extract_block(html, "content")
        description = html_to_markdown(content_html or "")
        if not description:
            raise ValueError("PCC detail HTML is missing content block")

        return {
            **summary,
            "title": self._extract_text_from_tag(html, "h1") or summary["title"],
            "agency": self._extract_field(html, "agency") or summary.get("agency", self.SOURCE_AGENCY),
            "tender_no": self._extract_field(html, "tender-no") or summary.get("tender_no", ""),
            "source_date": self._parse_date(self._extract_field(html, "date")) or summary.get("source_date"),
            "procurement_type": self._extract_field(html, "procurement-type") or summary.get("procurement_type", ""),
            "budget": self._extract_field(html, "budget"),
            "summary": self._extract_field(html, "summary") or summary.get("summary", ""),
            "description": description,
            "source_url": summary.get("source_url", summary["detail_url"]),
        }

    @classmethod
    def _build_content_markdown(cls, raw: dict[str, Any]) -> str:
        lines = [f"# {str(raw.get('title', '')).strip()}"]
        if raw.get("agency"):
            lines.append(f"**機關名稱**：{str(raw['agency']).strip()}")
        if raw.get("tender_no"):
            lines.append(f"**標案案號**：{str(raw['tender_no']).strip()}")
        if raw.get("procurement_type"):
            lines.append(f"**採購方式**：{str(raw['procurement_type']).strip()}")
        if raw.get("source_date"):
            lines.append(f"**公告日期**：{raw['source_date'].isoformat()}")
        if raw.get("budget"):
            lines.append(f"**預算金額**：{str(raw['budget']).strip()}")
        if raw.get("source_url"):
            lines.append(f"**原文連結**：{str(raw['source_url']).strip()}")
        if raw.get("summary"):
            lines.append(f"## 摘要\n{str(raw['summary']).strip()}")
        if raw.get("description"):
            lines.append(f"## 內容\n{str(raw['description']).strip()}")
        return "\n\n".join(lines)

    @staticmethod
    def _extract_field(html: str, class_name: str) -> str:
        pattern = rf'<(?:td|div|span|p)[^>]*class="[^"]*\b{re.escape(class_name)}\b[^"]*"[^>]*>(?P<value>.*?)</(?:td|div|span|p)>'
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if not match:
            return ""
        return PccAdapter._strip_tags(match.group("value"))

    @staticmethod
    def _extract_href(html: str, class_name: str) -> str:
        pattern = rf'<(?:td|div|span|p)[^>]*class="[^"]*\b{re.escape(class_name)}\b[^"]*"[^>]*>.*?<a[^>]*href="(?P<href>[^"]+)"'
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        return match.group("href").strip() if match else ""

    @staticmethod
    def _extract_block(html: str, class_name: str) -> str:
        pattern = rf'<div[^>]*class="[^"]*\b{re.escape(class_name)}\b[^"]*"[^>]*>(?P<value>.*?)</div>'
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        return match.group("value").strip() if match else ""

    @staticmethod
    def _extract_text_from_tag(html: str, tag: str) -> str:
        match = re.search(rf"<{tag}[^>]*>(?P<value>.*?)</{tag}>", html, re.IGNORECASE | re.DOTALL)
        return PccAdapter._strip_tags(match.group("value")) if match else ""

    @staticmethod
    def _parse_date(value: str) -> date | None:
        if not value:
            return None
        text = value.strip().replace("/", "-")
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None

    @staticmethod
    def _strip_tags(value: str) -> str:
        text = re.sub(r"<[^>]+>", " ", value)
        text = text.replace("&nbsp;", " ").replace("&amp;", "&")
        return " ".join(text.split())
