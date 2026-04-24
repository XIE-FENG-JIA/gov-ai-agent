from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

import requests

from src.core.models import PublicGovDoc
from src.sources._common import build_headers, request_with_proxy_bypass, throttle, with_fixture_fallback
from src.sources.base import BaseSourceAdapter

from .catalog import extract_dataset_id, load_resource_records
from .normalizer import expand_dataset_documents, normalize_document


class DataGovTwAdapter(BaseSourceAdapter):
    """Adapter for the public data.gov.tw front-end dataset search API."""

    SOURCE_AGENCY = "政府資料開放平臺"
    SEARCH_URL = "https://data.gov.tw/api/front/dataset/list"
    DEFAULT_FIXTURE_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "datagovtw"

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
        self._document_cache: dict[str, dict[str, Any]] = {}

    def list(self, since_date: date | None = None, limit: int = 3) -> Iterable[dict[str, Any]]:
        if limit <= 0:
            return []

        docs: list[dict[str, Any]] = []
        for raw in self._load_catalog(limit=limit):
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
        if normalized_id not in self._document_cache:
            self._load_catalog(limit=50, force_refresh=True)
        if normalized_id not in self._document_cache:
            raise KeyError(f"DataGovTw document not found: {normalized_id}")
        return self._document_cache[normalized_id]

    def normalize(self, raw: dict[str, Any]) -> PublicGovDoc:
        return normalize_document(raw, source_agency=self.SOURCE_AGENCY)

    def _load_catalog(self, *, limit: int, force_refresh: bool = False) -> list[dict[str, Any]]:
        if self._document_cache and not force_refresh and len(self._document_cache) >= limit:
            return list(self._document_cache.values())

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

        self._dataset_cache = {}
        self._document_cache = {}
        ordered_docs: list[dict[str, Any]] = []
        for dataset in datasets:
            if not isinstance(dataset, dict):
                continue
            dataset_id = extract_dataset_id(dataset)
            if not dataset_id:
                continue
            dataset_payload = {**dataset, "_fixture_fallback": result.used_fixture}
            self._dataset_cache[dataset_id] = dataset_payload
            for document in expand_dataset_documents(
                dataset_payload,
                fixture_fallback=result.used_fixture,
                source_agency=self.SOURCE_AGENCY,
                load_resource_records=self._load_resource_records,
            ):
                if document["id"] in self._document_cache:
                    continue
                self._document_cache[document["id"]] = document
                ordered_docs.append(document)
                if len(ordered_docs) >= limit:
                    return ordered_docs
        return ordered_docs

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

    def _load_resource_records(self, resource: dict[str, Any], *, fixture_fallback: bool) -> list[dict[str, Any]]:
        return load_resource_records(
            resource,
            load_fixture_resource=self._load_fixture_resource,
            request_resource_text=self._request_resource_text,
        )

    def _request_resource_text(self, resource_url: str) -> str:
        self._throttle()
        response = request_with_proxy_bypass(
            self.session,
            "get",
            resource_url,
            headers=build_headers(accept="application/json,text/csv,text/plain,*/*"),
            timeout=self.timeout,
        )
        response.raise_for_status()
        response.encoding = response.encoding or "utf-8"
        return response.text

    def _load_fixture_resource(self, resource_url: str) -> str:
        fixture_path = self.fixture_dir / resource_url.removeprefix("__fixture__/")
        return fixture_path.read_text(encoding="utf-8")

    def _throttle(self) -> None:
        self._last_request_time = throttle(self._last_request_time, self.rate_limit)
