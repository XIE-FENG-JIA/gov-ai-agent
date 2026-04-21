"""Adapter for data.gov.tw dataset resources that contain actual public-document rows."""

from __future__ import annotations

import json
import csv
import time
from collections.abc import Iterable
from datetime import date
from io import StringIO
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
        title = str(raw.get("title", "")).strip()
        if not title:
            raise ValueError("raw document payload is missing title")

        agency_name = str(raw.get("source_agency", "")).strip() or self.SOURCE_AGENCY
        return PublicGovDoc(
            source_id=str(raw.get("id", "")).strip(),
            source_url=str(raw.get("source_url", "")).strip(),
            source_agency=agency_name,
            source_doc_no=str(raw.get("source_doc_no", "")).strip() or None,
            source_date=raw.get("source_date"),
            doc_type=str(raw.get("doc_type", "")).strip() or "公告",
            raw_snapshot_path=None,
            crawl_date=date.today(),
            content_md=self._build_content_markdown(raw),
            synthetic=bool(raw.get("_fixture_fallback")),
            fixture_fallback=bool(raw.get("_fixture_fallback")),
        )

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
            dataset_id = self._extract_dataset_id(dataset)
            if not dataset_id:
                continue
            dataset_payload = {**dataset, "_fixture_fallback": result.used_fixture}
            self._dataset_cache[dataset_id] = dataset_payload
            for document in self._expand_dataset_documents(dataset_payload):
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
        body = str(raw.get("body", "")).strip()
        summary = str(raw.get("summary", "")).strip()
        agency_name = str(raw.get("source_agency", "")).strip()
        dataset_title = str(raw.get("dataset_title", "")).strip()
        source_doc_no = str(raw.get("source_doc_no", "")).strip()
        resource_name = str(raw.get("resource_name", "")).strip()
        tags = raw.get("tags", [])

        lines = [f"# {title}"]
        if agency_name:
            lines.append(f"**提供機關**：{agency_name}")
        if source_doc_no:
            lines.append(f"**文號**：{source_doc_no}")
        if dataset_title:
            lines.append(f"**資料集**：{dataset_title}")
        if resource_name:
            lines.append(f"**資源**：{resource_name}")
        if summary:
            lines.append(f"## 主旨\n{summary}")
        if body:
            lines.append(f"## 內容\n{body}")
        if isinstance(tags, list) and tags:
            clean_tags = [str(tag).strip() for tag in tags if str(tag).strip()]
            if clean_tags:
                lines.append(f"**標籤**：{', '.join(clean_tags)}")
        return "\n\n".join(lines)

    def _expand_dataset_documents(self, dataset: dict[str, Any]) -> list[dict[str, Any]]:
        dataset_id = self._extract_dataset_id(dataset)
        fixture_fallback = bool(dataset.get("_fixture_fallback"))
        documents: list[dict[str, Any]] = []
        for resource in self._extract_resources(dataset):
            records = self._load_resource_records(resource, fixture_fallback=fixture_fallback)
            for index, record in enumerate(records, start=1):
                document = self._build_document_entry(
                    dataset=dataset,
                    resource=resource,
                    record=record,
                    index=index,
                    fixture_fallback=fixture_fallback,
                )
                if document is None:
                    continue
                documents.append(document)
        if documents:
            return documents
        if self._looks_like_metadata_only_dataset(dataset):
            return []
        return []

    def _load_resource_records(self, resource: dict[str, Any], *, fixture_fallback: bool) -> list[dict[str, Any]]:
        resource_url = self._resource_url(resource)
        if not resource_url:
            return []
        if resource_url.startswith("__fixture__/"):
            text = self._load_fixture_resource(resource_url)
        else:
            text = self._request_resource_text(resource_url)
        if not text:
            return []

        resource_format = str(resource.get("format", resource.get("resource_format", ""))).strip().lower()
        if not resource_format:
            resource_format = self._guess_resource_format(resource_url, text)

        if resource_format == "csv":
            return self._parse_csv_records(text)
        if resource_format == "json":
            return self._parse_json_records(text)
        return []

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

    @staticmethod
    def _parse_json_records(text: str) -> list[dict[str, Any]]:
        payload = json.loads(text)
        return DataGovTwAdapter._coerce_record_list(payload)

    @staticmethod
    def _parse_csv_records(text: str) -> list[dict[str, Any]]:
        reader = csv.DictReader(StringIO(text))
        return [dict(row) for row in reader if isinstance(row, dict)]

    @classmethod
    def _coerce_record_list(cls, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("data", "records", "results", "items", "rows", "entries"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
                if isinstance(value, dict):
                    nested = cls._coerce_record_list(value)
                    if nested:
                        return nested
            if any(not isinstance(value, (dict, list)) for value in payload.values()):
                return [payload]
        return []

    def _build_document_entry(
        self,
        *,
        dataset: dict[str, Any],
        resource: dict[str, Any],
        record: dict[str, Any],
        index: int,
        fixture_fallback: bool,
    ) -> dict[str, Any] | None:
        title = self._pick_text(record, "title", "subject", "name", "標題", "主旨", "公告標題")
        summary = self._pick_text(record, "summary", "abstract", "description", "主旨", "說明")
        body = self._pick_text(record, "content", "body", "text", "內容", "公告內容", "說明")
        source_doc_no = self._pick_text(record, "doc_no", "document_no", "number", "docNumber", "文號", "發文字號")
        source_url = self._pick_text(record, "url", "link", "source_url", "詳情連結", "網址")
        if not title or not (body or summary or source_doc_no):
            return None

        dataset_id = self._extract_dataset_id(dataset)
        record_key = self._pick_text(record, "id", "doc_id", "document_id", "uuid", "文號") or f"row{index}"
        safe_record_key = self._slugify(record_key)
        safe_resource_key = self._slugify(
            self._pick_text(resource, "id", "name", "resource_id", "resource_name") or f"resource{index}"
        )
        parsed_date = self._extract_source_date(record) or self._extract_source_date(dataset)
        source_url = source_url or self._resource_url(resource) or OPENDATA_DETAIL_URL.format(dataset_id=dataset_id)
        agency = self._pick_text(record, "agency", "agency_name", "publisher", "機關", "提供機關") or str(
            dataset.get("agency_name", "")
        ).strip()
        return {
            "id": f"{dataset_id}--{safe_resource_key}--{safe_record_key}",
            "title": title,
            "summary": summary,
            "body": body,
            "source_date": parsed_date,
            "source_url": source_url,
            "source_agency": agency or self.SOURCE_AGENCY,
            "source_doc_no": source_doc_no or record_key,
            "doc_type": self._detect_doc_type(title=title, body=body, summary=summary),
            "dataset_title": str(dataset.get("title", "")).strip(),
            "resource_name": self._pick_text(resource, "name", "description", "title"),
            "tags": dataset.get("tags", []),
            "_fixture_fallback": fixture_fallback,
        }

    @staticmethod
    def _extract_resources(dataset: dict[str, Any]) -> list[dict[str, Any]]:
        for key in ("resources", "distributions", "distribution"):
            value = dataset.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _resource_url(resource: dict[str, Any]) -> str:
        for key in ("download_url", "url", "resource_url", "downloadURL", "accessURL", "href"):
            value = resource.get(key)
            if value:
                return str(value).strip()
        return ""

    @staticmethod
    def _pick_text(record: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = record.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return ""

    @staticmethod
    def _slugify(value: str) -> str:
        chars = [char.lower() if char.isalnum() else "-" for char in value.strip()]
        slug = "".join(chars).strip("-")
        while "--" in slug:
            slug = slug.replace("--", "-")
        return slug or "item"

    @staticmethod
    def _guess_resource_format(resource_url: str, text: str) -> str:
        lower_url = resource_url.lower()
        if lower_url.endswith(".csv"):
            return "csv"
        if lower_url.endswith(".json"):
            return "json"
        stripped = text.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            return "json"
        return "csv" if "," in text.partition("\n")[0] else ""

    @staticmethod
    def _detect_doc_type(*, title: str, body: str, summary: str) -> str:
        probe = f"{title}\n{summary}\n{body}"
        if "公告" in probe:
            return "公告"
        if "函" in probe:
            return "函"
        return "公告"

    @staticmethod
    def _looks_like_metadata_only_dataset(dataset: dict[str, Any]) -> bool:
        return bool(dataset.get("resources") or dataset.get("distributions") or dataset.get("distribution"))
