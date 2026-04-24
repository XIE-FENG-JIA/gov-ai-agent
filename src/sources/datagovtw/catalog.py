from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from io import StringIO
from typing import Any


def extract_dataset_id(raw: dict[str, Any]) -> str:
    return str(raw.get("nid", raw.get("datasetId", ""))).strip()


def extract_resources(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("resources", "distributions", "distribution"):
        value = dataset.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def resource_url(resource: dict[str, Any]) -> str:
    for key in ("download_url", "url", "resource_url", "downloadURL", "accessURL", "href"):
        value = resource.get(key)
        if value:
            return str(value).strip()
    return ""


def parse_json_records(text: str) -> list[dict[str, Any]]:
    payload = json.loads(text)
    return coerce_record_list(payload)


def parse_csv_records(text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(StringIO(text))
    return [dict(row) for row in reader if isinstance(row, dict)]


def coerce_record_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "records", "results", "items", "rows", "entries"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                nested = coerce_record_list(value)
                if nested:
                    return nested
        if any(not isinstance(value, (dict, list)) for value in payload.values()):
            return [payload]
    return []


def guess_resource_format(resource_url_value: str, text: str) -> str:
    lower_url = resource_url_value.lower()
    if lower_url.endswith(".csv"):
        return "csv"
    if lower_url.endswith(".json"):
        return "json"
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return "json"
    return "csv" if "," in text.partition("\n")[0] else ""


def load_resource_records(
    resource: dict[str, Any],
    *,
    load_fixture_resource: callable,
    request_resource_text: callable,
) -> list[dict[str, Any]]:
    resource_url_value = resource_url(resource)
    if not resource_url_value:
        return []
    if resource_url_value.startswith("__fixture__/"):
        text = load_fixture_resource(resource_url_value)
    else:
        text = request_resource_text(resource_url_value)
    if not text:
        return []

    resource_format = str(resource.get("format", resource.get("resource_format", ""))).strip().lower()
    if not resource_format:
        resource_format = guess_resource_format(resource_url_value, text)

    if resource_format == "csv":
        return parse_csv_records(text)
    if resource_format == "json":
        return parse_json_records(text)
    return []


def looks_like_metadata_only_dataset(dataset: dict[str, Any]) -> bool:
    return bool(dataset.get("resources") or dataset.get("distributions") or dataset.get("distribution"))
