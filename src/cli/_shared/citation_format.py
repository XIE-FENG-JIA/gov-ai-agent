"""Public interface for citation/regulation mapping shared between
``cite_cmd`` and ``generate/export``.

Extracted from ``cite_cmd`` to break the iceberg coupling described in
T13.2 of ``openspec/changes/13-cli-fat-rotate-v3/tasks.md``.
"""
from pathlib import Path

import yaml

# Default mapping file path (relative to working directory)
MAPPING_PATH = Path("kb_data/regulation_doc_type_mapping.yaml")


def load_citation_mapping(mapping_path: Path = MAPPING_PATH) -> dict:
    """Load the regulation-to-doc-type mapping table.

    Raises ``FileNotFoundError`` with an actionable message when the file
    is missing.
    """
    if not mapping_path.exists():
        raise FileNotFoundError(
            f"找不到法規映射表：{mapping_path}\n"
            "請確認工作目錄正確，或指定 --mapping 路徑。"
        )
    with mapping_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("regulations", {})


def filter_applicable_citations(regulations: dict, doc_type: str) -> list[dict]:
    """Return regulations applicable to *doc_type*, sorted by name.

    Each result dict contains ``name``, ``pcode``, ``description``,
    ``source_level``, and ``cite_format`` keys.
    """
    result = []
    for name, meta in regulations.items():
        applicable = meta.get("applicable_doc_types", [])
        if doc_type in applicable:
            result.append(
                {
                    "name": name,
                    "pcode": meta.get("pcode", ""),
                    "description": meta.get("description", ""),
                    "source_level": meta.get("source_level", "A"),
                    "cite_format": f"依據《{name}》",
                }
            )
    return sorted(result, key=lambda x: x["name"])
