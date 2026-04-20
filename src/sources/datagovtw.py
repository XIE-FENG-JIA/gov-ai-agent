"""Adapter for data.gov.tw dataset metadata."""

from __future__ import annotations

import json
import time
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

import requests

from src.core.models import PublicGovDoc
from src.knowledge.fetchers.constants import OPENDATA_DETAIL_URL
from src.sources._common import build_headers, request_with_proxy_bypass, throttle, with_fixture_fallback
from src.sources.base import BaseSourceAdapter


class DataGovTwAdapter(BaseSourceAdapter):
    """Adapter for the public data.gov.tw front-end dataset search API."""

    SOURCE_AGENCY = "政府資料開放平臺"
    SEARCH_URL = "https://data.gov.tw/api/front/dataset/list"
    DEFAULT_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "datagovtw"

    def __init__(
        self,
        *,
        session: requests.sessions.Session | None = None,
        search_url: str = SEARCH_URL,
        keyword: str = "公文",
        rate_limit: float = 2.0,
        timeout: float = 30.0,
        fixture_dir: Path | None = None,
    ) -> None:
        self.session = session or requests.Session()
        self.search_url = search_url
        self.keyword = keyword
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.fixture_dir = fixture_dir if fixture_dir is not None else self.DEFAULT_FIXTURE_DIR
        self._last_request_time = 0.0
        self._dataset_cache: dict[str, dict[str, Any]] = {}

    def list(self, since_date: date | None = None, limit: int = 3) -> Iterable[dict[str, Any]]:
        if limit <= 0:
            return []

        docs: list[dict[str, Any]] = []
        for raw in self._load_catalog(limit=limit):
            source_date = self._extract_source_date(raw)
            if since_date is not None and source_date is not None and source_date < since_date:
                continue

            dataset_id = self._extract_dataset_id(raw)
            if not dataset_id:
                continue

            docs.append(
                {
                    "id": dataset_id,
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
        if normalized_id not in self._dataset_cache:
            self._load_catalog(limit=50, force_refresh=True)
        if normalized_id not in self._dataset_cache:
            raise KeyError(f"DataGovTw dataset not found: {normalized_id}")
        return self._dataset_cache[normalized_id]

    def normalize(self, raw: dict[str, Any]) -> PublicGovDoc:
        dataset_id = self._extract_dataset_id(raw)
        if not dataset_id:
            raise ValueError("raw dataset payload is missing nid/datasetId")

        title = str(raw.get("title", "")).strip()
        if not title:
            raise ValueError("raw dataset payload is missing title")

        agency_name = str(raw.get("agency_name", "")).strip() or self.SOURCE_AGENCY
        return PublicGovDoc(
            source_id=dataset_id,
            source_url=OPENDATA_DETAIL_URL.format(dataset_id=dataset_id),
            source_agency=agency_name,
            source_doc_no=dataset_id,
            source_date=self._extract_source_date(raw),
            doc_type="開放資料",
            raw_snapshot_path=None,
            crawl_date=date.today(),
            content_md=self._build_content_markdown(raw),
            synthetic=bool(raw.get("_fixture_fallback")),
            fixture_fallback=bool(raw.get("_fixture_fallback")),
        )

    def _load_catalog(self, *, limit: int, force_refresh: bool = False) -> list[dict[str, Any]]:
        if self._dataset_cache and not force_refresh and len(self._dataset_cache) >= limit:
            return list(self._dataset_cache.values())

        payload = {
            "bool": [{"fulltext": {"value": self.keyword}}],
            "filter": [],
            "page_num": 1,
            "page_limit": max(limit, 3),
            "tids": [],
            "sort": "_score_desc",
        }
        result = with_fixture_fallback(
            lambda: self._request_json(payload).json(),
            self._load_fixture_catalog,
            handled_exceptions=(requests.RequestException, ValueError, TypeError),
        )
        data = result.value
        payload_data = data.get("payload", {}) if isinstance(data, dict) else {}
        datasets = payload_data.get("search_result", []) if isinstance(payload_data, dict) else []
        if not isinstance(datasets, list):
            datasets = []

        self._dataset_cache = {
            dataset_id: {
                **dataset,
                "_fixture_fallback": result.used_fixture,
            }
            for dataset in datasets
            if isinstance(dataset, dict)
            for dataset_id in [self._extract_dataset_id(dataset)]
            if dataset_id
        }
        return list(self._dataset_cache.values())

    def _request_json(self, payload: dict[str, Any]) -> requests.Response:
        self._throttle()
        response = request_with_proxy_bypass(
            self.session,
            "post",
            self.search_url,
            json=payload,
            headers=build_headers(
                accept="application/json",
                extra={"Content-Type": "application/json"},
            ),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response

    def _load_fixture_catalog(self, exc: Exception) -> dict[str, Any]:
        if not self.fixture_dir.exists():
            raise exc

        datasets: list[dict[str, Any]] = []
        for path in sorted(self.fixture_dir.glob("*.json")):
            datasets.append(json.loads(path.read_text(encoding="utf-8")))
        return {"payload": {"search_result": datasets}}

    def _throttle(self) -> None:
        self._last_request_time = throttle(self._last_request_time, self.rate_limit)

    @staticmethod
    def _extract_dataset_id(raw: dict[str, Any]) -> str:
        return str(raw.get("nid", raw.get("datasetId", ""))).strip()

    @staticmethod
    def _extract_source_date(raw: dict[str, Any]) -> date | None:
        for key in (
            "metadata_modified",
            "modified",
            "modified_date",
            "update_time",
            "updateDate",
            "publish_time",
            "created",
        ):
            value = raw.get(key)
            if not value:
                continue
            text = str(value).strip().replace("/", "-")
            try:
                return date.fromisoformat(text[:10])
            except ValueError:
                continue
        return None

    @classmethod
    def _build_content_markdown(cls, raw: dict[str, Any]) -> str:
        title = str(raw.get("title", "")).strip()
        description = str(raw.get("content", raw.get("description", ""))).strip()
        agency_name = str(raw.get("agency_name", "")).strip()
        category_name = str(raw.get("category_name", "")).strip()
        topic_name = str(raw.get("topic_name", "")).strip()
        update_freq = str(raw.get("updatefreq_desc", "")).strip()
        tags = raw.get("tags", [])

        lines = [f"# {title}"]
        if agency_name:
            lines.append(f"**提供機關**：{agency_name}")
        if description:
            lines.append(f"## 說明\n{description}")
        if category_name:
            lines.append(f"**服務分類**：{category_name}")
        if topic_name:
            lines.append(f"**主題**：{topic_name}")
        if update_freq:
            lines.append(f"**更新頻率**：{update_freq}")
        if isinstance(tags, list) and tags:
            clean_tags = [str(tag).strip() for tag in tags if str(tag).strip()]
            if clean_tags:
                lines.append(f"**標籤**：{', '.join(clean_tags)}")
        return "\n\n".join(lines)
