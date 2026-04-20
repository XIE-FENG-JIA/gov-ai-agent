"""Adapter for the Ministry of Justice law database."""

from __future__ import annotations

import io
import json
import time
import zipfile
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

import requests

from src.core.models import PublicGovDoc
from src.knowledge.fetchers.constants import LAW_API_URL, LAW_DETAIL_URL
from src.sources._common import build_headers, request_with_proxy_bypass, throttle, with_fixture_fallback
from src.sources.base import BaseSourceAdapter


class MojLawAdapter(BaseSourceAdapter):
    """Adapter for https://law.moj.gov.tw/ using the public JSON feed."""

    SOURCE_AGENCY = "法務部全國法規資料庫"
    USER_AGENT = "GovAI-Agent/1.0 (research; contact: local-dev)"
    DEFAULT_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "mojlaw"

    def __init__(
        self,
        *,
        session: requests.sessions.Session | None = None,
        api_url: str = LAW_API_URL,
        rate_limit: float = 2.0,
        timeout: float = 60.0,
        fixture_dir: Path | None = None,
    ) -> None:
        self.session = session or requests.Session()
        self.api_url = api_url
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.fixture_dir = fixture_dir if fixture_dir is not None else self.DEFAULT_FIXTURE_DIR
        self._last_request_time = 0.0
        self._law_cache: dict[str, dict[str, Any]] = {}

    def list(self, since_date: date | None = None, limit: int = 3) -> Iterable[dict[str, Any]]:
        if limit <= 0:
            return []

        docs: list[dict[str, Any]] = []
        for raw in self._load_catalog():
            source_date = self._extract_source_date(raw)
            if since_date is not None and source_date is not None and source_date < since_date:
                continue
            doc_id = str(raw.get("PCode", "")).strip()
            if not doc_id:
                continue
            docs.append(
                {
                    "id": doc_id,
                    "title": raw.get("LawName", "").strip(),
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
        if normalized_id not in self._law_cache:
            self._load_catalog(force_refresh=True)
        if normalized_id not in self._law_cache:
            raise KeyError(f"MojLaw document not found: {normalized_id}")
        return self._law_cache[normalized_id]

    def normalize(self, raw: dict[str, Any]) -> PublicGovDoc:
        source_id = str(raw.get("PCode", "")).strip()
        if not source_id:
            raise ValueError("raw law payload is missing PCode")
        law_name = str(raw.get("LawName", "")).strip()
        if not law_name:
            raise ValueError("raw law payload is missing LawName")

        return PublicGovDoc(
            source_id=source_id,
            source_url=LAW_DETAIL_URL.format(pcode=source_id),
            source_agency=self.SOURCE_AGENCY,
            source_doc_no=source_id,
            source_date=self._extract_source_date(raw),
            doc_type="法規",
            raw_snapshot_path=None,
            crawl_date=date.today(),
            content_md=self._build_content_markdown(law_name, raw.get("LawArticles", [])),
            synthetic=bool(raw.get("_fixture_fallback")),
            fixture_fallback=bool(raw.get("_fixture_fallback")),
        )

    def _load_catalog(self, *, force_refresh: bool = False) -> list[dict[str, Any]]:
        if self._law_cache and not force_refresh:
            return list(self._law_cache.values())

        result = with_fixture_fallback(
            lambda: self._extract_laws_from_response(self._request_json().content),
            self._load_fixture_catalog,
            handled_exceptions=(requests.RequestException, ValueError, TypeError),
        )
        laws = result.value
        self._law_cache = {
            str(law.get("PCode", "")).strip(): {
                **law,
                "_fixture_fallback": result.used_fixture,
            }
            for law in laws
            if str(law.get("PCode", "")).strip()
        }
        return list(self._law_cache.values())

    def _request_json(self) -> requests.Response:
        self._throttle()
        response = request_with_proxy_bypass(
            self.session,
            "get",
            self.api_url,
            headers=build_headers(accept="application/json", user_agent=self.USER_AGENT),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response

    def _load_fixture_catalog(self, exc: Exception) -> list[dict[str, Any]]:
        if not self.fixture_dir.exists():
            raise exc

        laws: list[dict[str, Any]] = []
        for path in sorted(self.fixture_dir.glob("*.json")):
            laws.append(json.loads(path.read_text(encoding="utf-8")))
        return laws

    def _throttle(self) -> None:
        self._last_request_time = throttle(self._last_request_time, self.rate_limit)

    @staticmethod
    def _extract_laws_from_response(data: bytes) -> list[dict[str, Any]]:
        raw_list: list[dict[str, Any]] = []

        def _unwrap_json(parsed: Any) -> list[dict[str, Any]]:
            if isinstance(parsed, dict):
                if isinstance(parsed.get("Laws"), list):
                    return parsed["Laws"]
                return [parsed]
            if isinstance(parsed, list):
                return parsed
            return []

        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for name in zf.namelist():
                    if not name.endswith(".json"):
                        continue
                    raw_list.extend(_unwrap_json(json.loads(zf.read(name))))
        except zipfile.BadZipFile:
            raw_list.extend(_unwrap_json(json.loads(data)))

        return [item for item in raw_list if isinstance(item, dict)]

    @staticmethod
    def _extract_source_date(raw: dict[str, Any]) -> date | None:
        for key in ("LawModifiedDate", "LawDate", "ModifiedDate", "Date"):
            value = raw.get(key)
            if not value:
                continue
            text = str(value).strip().replace("/", "-")
            try:
                return date.fromisoformat(text[:10])
            except ValueError:
                continue
        return None

    @staticmethod
    def _build_content_markdown(law_name: str, articles: Any) -> str:
        lines = [f"# {law_name}"]
        if not isinstance(articles, list):
            return "\n\n".join(lines)

        for article in articles:
            if not isinstance(article, dict):
                continue
            number = str(article.get("ArticleNo", "")).strip()
            content = str(article.get("ArticleContent", "")).strip()
            if number and content:
                lines.append(f"### {number}\n{content}")
            elif content:
                lines.append(content)

        return "\n\n".join(lines)
