"""Adapter for Ministry of Health and Welfare RSS feeds."""

from __future__ import annotations

import time
import defusedxml.ElementTree as ET
from collections.abc import Iterable
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import requests

from src.core.models import PublicGovDoc
from src.knowledge.fetchers.base import html_to_markdown
from src.sources._common import build_headers, request_with_proxy_bypass, throttle, with_fixture_fallback
from src.sources.base import BaseSourceAdapter


class MohwRssAdapter(BaseSourceAdapter):
    """Adapter for MOHW public RSS feeds."""

    SOURCE_AGENCY = "衛生福利部"
    FEED_URL = "https://www.mohw.gov.tw/rss-18-1.html"
    DEFAULT_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "mohw_rss" / "feed.xml"

    def __init__(
        self,
        *,
        session: requests.sessions.Session | None = None,
        feed_url: str = FEED_URL,
        rate_limit: float = 2.0,
        timeout: float = 30.0,
        fixture_path: Path | None = None,
    ) -> None:
        self.session = session or requests.Session()
        self.feed_url = feed_url
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.fixture_path = fixture_path if fixture_path is not None else self.DEFAULT_FIXTURE_PATH
        self._last_request_time = 0.0
        self._entry_cache: dict[str, dict[str, Any]] = {}

    def list(self, since_date: date | None = None, limit: int = 3) -> Iterable[dict[str, Any]]:
        if limit <= 0:
            return []

        docs: list[dict[str, Any]] = []
        for raw in self._load_feed():
            source_date = self._extract_source_date(raw)
            if since_date is not None and source_date is not None and source_date < since_date:
                continue

            entry_id = self._extract_entry_id(raw)
            if not entry_id:
                continue

            docs.append(
                {
                    "id": entry_id,
                    "title": str(raw.get("title", "")).strip(),
                    "date": source_date,
                }
            )
            if len(docs) == limit:
                break
        return docs

    def fetch(self, doc_id: str) -> dict[str, Any]:
        normalized_id = doc_id.strip()
        if not normalized_id:
            raise ValueError("doc_id must not be blank")
        if normalized_id not in self._entry_cache:
            self._load_feed(force_refresh=True)
        if normalized_id not in self._entry_cache:
            raise KeyError(f"MOHW RSS entry not found: {normalized_id}")
        return self._entry_cache[normalized_id]

    def normalize(self, raw: dict[str, Any]) -> PublicGovDoc:
        entry_id = self._extract_entry_id(raw)
        title = str(raw.get("title", "")).strip()
        link = str(raw.get("link", "")).strip()
        if not entry_id or not title or not link:
            raise ValueError("raw RSS payload is missing id/title/link")

        return PublicGovDoc(
            source_id=entry_id,
            source_url=link,
            source_agency=self.SOURCE_AGENCY,
            source_doc_no=entry_id,
            source_date=self._extract_source_date(raw),
            doc_type="公告",
            raw_snapshot_path=None,
            crawl_date=date.today(),
            content_md=self._build_content_markdown(raw),
            synthetic=bool(raw.get("_fixture_fallback")),
            fixture_fallback=bool(raw.get("_fixture_fallback")),
        )

    def _load_feed(self, *, force_refresh: bool = False) -> list[dict[str, Any]]:
        if self._entry_cache and not force_refresh:
            return list(self._entry_cache.values())

        result = with_fixture_fallback(
            lambda: self._parse_feed(self._request_feed().text),
            self._load_fixture_feed,
            handled_exceptions=(requests.RequestException, ET.ParseError, ValueError, TypeError),
        )
        entries = result.value
        self._entry_cache = {
            entry_id: {
                **entry,
                "_fixture_fallback": result.used_fixture,
            }
            for entry in entries
            if isinstance(entry, dict)
            for entry_id in [self._extract_entry_id(entry)]
            if entry_id
        }
        return list(self._entry_cache.values())

    def _request_feed(self) -> requests.Response:
        self._throttle()
        response = request_with_proxy_bypass(
            self.session,
            "get",
            self.feed_url,
            headers=build_headers(accept="application/rss+xml, application/xml, text/xml"),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response

    def _load_fixture_feed(self, exc: Exception) -> list[dict[str, Any]]:
        if not self.fixture_path.exists():
            raise exc
        return self._parse_feed(self.fixture_path.read_text(encoding="utf-8"))

    def _throttle(self) -> None:
        self._last_request_time = throttle(self._last_request_time, self.rate_limit)

    @staticmethod
    def _parse_feed(xml_text: str) -> list[dict[str, Any]]:
        root = ET.fromstring(xml_text)
        entries: list[dict[str, Any]] = []
        for item in root.findall("./channel/item"):
            raw = {
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "description": (item.findtext("description") or "").strip(),
                "pubDate": (item.findtext("pubDate") or "").strip(),
                "guid": (item.findtext("guid") or "").strip(),
            }
            if raw["title"] and raw["link"]:
                entries.append(raw)
        return entries

    @staticmethod
    def _extract_entry_id(raw: dict[str, Any]) -> str:
        return str(raw.get("guid", raw.get("link", ""))).strip() or str(raw.get("link", "")).strip()

    @staticmethod
    def _extract_source_date(raw: dict[str, Any]) -> date | None:
        value = str(raw.get("pubDate", "")).strip()
        if not value:
            return None
        try:
            return parsedate_to_datetime(value).date()
        except (TypeError, ValueError, IndexError, OverflowError):
            pass

        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(value[:19], fmt).date()
            except ValueError:
                continue
        return None

    @classmethod
    def _build_content_markdown(cls, raw: dict[str, Any]) -> str:
        title = str(raw.get("title", "")).strip()
        link = str(raw.get("link", "")).strip()
        description = html_to_markdown(str(raw.get("description", "")).strip())
        published_at = cls._extract_source_date(raw)

        lines = [f"# {title}"]
        if published_at is not None:
            lines.append(f"**發布日期**：{published_at.isoformat()}")
        if link:
            lines.append(f"**原文連結**：{link}")
        if description:
            lines.append(f"## 摘要\n{description}")
        return "\n\n".join(lines)
