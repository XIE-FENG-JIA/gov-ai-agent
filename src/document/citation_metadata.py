import json
import re
import zipfile
from xml.etree import ElementTree as ET

REFERENCE_DEFINITION_RE = re.compile(
    r"^\[\^(?P<index>\d+)\]:\s*\[Level\s+(?P<level>[A-Z])\]\s*"
    r"(?P<title>.*?)(?:\s+\|\s+URL:\s+(?P<url>\S+))?(?:\s+\|\s+Hash:\s+(?P<hash>[A-Za-z0-9]+))?\s*$"
)

CITATION_EXPORT_METADATA_KEYS = (
    "source_doc_ids",
    "citation_count",
    "ai_generated",
    "engine",
    "citation_sources_json",
)

CUSTOM_PROPERTIES_NS = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
DOC_PROPS_VT_NS = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
CUSTOM_PROPERTIES_XML_PATH = "docProps/custom.xml"


def extract_reference_entries(draft_text: str) -> list[dict[str, str | int]]:
    entries: list[dict[str, str | int]] = []
    for raw_line in draft_text.splitlines():
        match = REFERENCE_DEFINITION_RE.match(raw_line.strip())
        if not match:
            continue
        entries.append(
            {
                "index": int(match.group("index")),
                "source_level": match.group("level"),
                "title": match.group("title").strip(),
                "source_url": (match.group("url") or "").strip(),
                "content_hash": (match.group("hash") or "").strip(),
            }
        )
    return entries


def match_reviewed_source(entry: dict[str, str | int], reviewed_sources: list[dict]) -> dict:
    for source in reviewed_sources:
        if source.get("index") == entry["index"]:
            return source
    for source in reviewed_sources:
        if entry["content_hash"] and source.get("content_hash") == entry["content_hash"]:
            return source
    for source in reviewed_sources:
        if entry["source_url"] and source.get("source_url") == entry["source_url"]:
            return source
    for source in reviewed_sources:
        if source.get("title") == entry["title"]:
            return source
    return {}


def build_citation_export_metadata(
    draft_text: str,
    citation_metadata: dict | None,
) -> dict[str, object] | None:
    reference_entries = extract_reference_entries(draft_text)
    if not reference_entries and not citation_metadata:
        return None

    citation_metadata = citation_metadata or {}
    reviewed_sources = list(citation_metadata.get("reviewed_sources") or citation_metadata.get("sources") or [])
    engine = str(citation_metadata.get("engine") or "").strip()
    ai_generated = bool(citation_metadata.get("ai_generated", True))

    source_doc_ids: list[str] = []
    verification_sources: list[dict[str, object]] = []
    for entry in reference_entries:
        matched = match_reviewed_source(entry, reviewed_sources)
        source_doc_id = (
            matched.get("record_id")
            or matched.get("source_doc_id")
            or matched.get("content_hash")
            or entry["content_hash"]
            or matched.get("source_url")
            or entry["source_url"]
            or matched.get("title")
            or entry["title"]
        )
        if source_doc_id:
            source_doc_ids.append(str(source_doc_id))

        verification_sources.append(
            {
                "index": int(entry["index"]),
                "title": str(entry["title"]),
                "source_level": str(matched.get("source_level") or entry["source_level"]),
                "source_url": str(matched.get("source_url") or entry["source_url"]),
                "content_hash": str(matched.get("content_hash") or entry["content_hash"]),
                "source_doc_id": str(source_doc_id or ""),
            }
        )

    ordered_source_doc_ids = list(dict.fromkeys(source_doc_ids))
    return {
        "source_doc_ids": json.dumps(ordered_source_doc_ids, ensure_ascii=False),
        "citation_count": len(reference_entries),
        "ai_generated": ai_generated,
        "engine": engine,
        "citation_sources_json": json.dumps(verification_sources, ensure_ascii=False),
    }


def read_docx_citation_metadata(path: str) -> dict[str, object]:
    with zipfile.ZipFile(path, "r") as archive:
        if CUSTOM_PROPERTIES_XML_PATH not in archive.namelist():
            return {}
        custom_xml = archive.read(CUSTOM_PROPERTIES_XML_PATH)

    root = ET.fromstring(custom_xml)
    raw_values: dict[str, str] = {}
    for prop in root.findall(f"{{{CUSTOM_PROPERTIES_NS}}}property"):
        name = prop.get("name", "")
        if name not in CITATION_EXPORT_METADATA_KEYS:
            continue
        for child in list(prop):
            if child.tag in {
                f"{{{DOC_PROPS_VT_NS}}}lpwstr",
                f"{{{DOC_PROPS_VT_NS}}}i4",
                f"{{{DOC_PROPS_VT_NS}}}bool",
            }:
                raw_values[name] = child.text or ""
                break

    if not raw_values:
        return {}

    return {
        "source_doc_ids": json.loads(raw_values.get("source_doc_ids", "[]")),
        "citation_count": int(raw_values.get("citation_count", "0") or 0),
        "ai_generated": raw_values.get("ai_generated", "").lower() == "true",
        "engine": raw_values.get("engine", ""),
        "citation_sources_json": json.loads(raw_values.get("citation_sources_json", "[]")),
    }
