from __future__ import annotations

from datetime import date
from typing import Any

from src.core.models import PublicGovDoc
from src.knowledge.fetchers.constants import OPENDATA_DETAIL_URL

from .catalog import extract_dataset_id, extract_resources, looks_like_metadata_only_dataset, resource_url


def extract_source_date(raw: dict[str, Any]) -> date | None:
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


def build_content_markdown(raw: dict[str, Any]) -> str:
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


def normalize_document(raw: dict[str, Any], *, source_agency: str) -> PublicGovDoc:
    title = str(raw.get("title", "")).strip()
    if not title:
        raise ValueError("raw document payload is missing title")

    agency_name = str(raw.get("source_agency", "")).strip() or source_agency
    return PublicGovDoc(
        source_id=str(raw.get("id", "")).strip(),
        source_url=str(raw.get("source_url", "")).strip(),
        source_agency=agency_name,
        source_doc_no=str(raw.get("source_doc_no", "")).strip() or None,
        source_date=raw.get("source_date"),
        doc_type=str(raw.get("doc_type", "")).strip() or "公告",
        raw_snapshot_path=None,
        crawl_date=date.today(),
        content_md=build_content_markdown(raw),
        synthetic=bool(raw.get("_fixture_fallback")),
        fixture_fallback=bool(raw.get("_fixture_fallback")),
    )


def expand_dataset_documents(
    dataset: dict[str, Any],
    *,
    fixture_fallback: bool,
    source_agency: str,
    load_resource_records: callable,
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for resource in extract_resources(dataset):
        records = load_resource_records(resource, fixture_fallback=fixture_fallback)
        for index, record in enumerate(records, start=1):
            document = build_document_entry(
                dataset=dataset,
                resource=resource,
                record=record,
                index=index,
                fixture_fallback=fixture_fallback,
                source_agency=source_agency,
            )
            if document is not None:
                documents.append(document)
    if documents or looks_like_metadata_only_dataset(dataset):
        return documents
    return []


def build_document_entry(
    *,
    dataset: dict[str, Any],
    resource: dict[str, Any],
    record: dict[str, Any],
    index: int,
    fixture_fallback: bool,
    source_agency: str,
) -> dict[str, Any] | None:
    title = pick_text(record, "title", "subject", "name", "標題", "主旨", "公告標題")
    summary = pick_text(record, "summary", "abstract", "description", "主旨", "說明")
    body = pick_text(record, "content", "body", "text", "內容", "公告內容", "說明")
    source_doc_no = pick_text(record, "doc_no", "document_no", "number", "docNumber", "文號", "發文字號")
    source_url_value = pick_text(record, "url", "link", "source_url", "詳情連結", "網址")
    if not title or not (body or summary or source_doc_no):
        return None

    dataset_id = extract_dataset_id(dataset)
    record_key = pick_text(record, "id", "doc_id", "document_id", "uuid", "文號") or f"row{index}"
    safe_record_key = slugify(record_key)
    safe_resource_key = slugify(pick_text(resource, "id", "name", "resource_id", "resource_name") or f"resource{index}")
    parsed_date = extract_source_date(record) or extract_source_date(dataset)
    source_url_value = source_url_value or resource_url(resource) or OPENDATA_DETAIL_URL.format(dataset_id=dataset_id)
    agency = pick_text(record, "agency", "agency_name", "publisher", "機關", "提供機關") or str(
        dataset.get("agency_name", "")
    ).strip()
    return {
        "id": f"{dataset_id}--{safe_resource_key}--{safe_record_key}",
        "title": title,
        "summary": summary,
        "body": body,
        "source_date": parsed_date,
        "source_url": source_url_value,
        "source_agency": agency or source_agency,
        "source_doc_no": source_doc_no or record_key,
        "doc_type": detect_doc_type(title=title, body=body, summary=summary),
        "dataset_title": str(dataset.get("title", "")).strip(),
        "resource_name": pick_text(resource, "name", "description", "title"),
        "tags": dataset.get("tags", []),
        "_fixture_fallback": fixture_fallback,
    }


def pick_text(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def slugify(value: str) -> str:
    chars = [char.lower() if char.isalnum() else "-" for char in value.strip()]
    slug = "".join(chars).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "item"


def detect_doc_type(*, title: str, body: str, summary: str) -> str:
    probe = f"{title}\n{summary}\n{body}"
    if "公告" in probe:
        return "公告"
    if "函" in probe:
        return "函"
    return "公告"
