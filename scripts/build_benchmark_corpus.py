#!/usr/bin/env python3
"""建置公文品質 benchmark 題庫（MVP 30 題預設：函/公告/簽 各 10 題）。"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXAMPLES_DIR = ROOT / "kb_data" / "examples"
DEFAULT_OUTPUT_PATH = ROOT / "benchmark" / "mvp30_corpus.json"

DEFAULT_DOC_TYPES = ("函", "公告", "簽")

STRICT_REQUEST_DEFAULTS = {
    "skip_review": False,
    "ralph_loop": True,
    "ralph_max_cycles": 2,
    "ralph_target_score": 1.0,
    "use_graph": False,
    "max_rounds": 2,
    "output_docx": False,
}

_TYPE_PREFIX_MAP = [
    ("announcement_", "公告", "announcement"),
    ("han_", "函", "han"),
    ("sign_", "簽", "sign"),
    ("shuhan_", "書函", "shuhan"),
    ("ling_", "令", "ling"),
    ("decree_", "令", "ling"),
    ("meeting_", "開會通知單", "meeting"),
    ("chen_", "呈", "chen"),
    ("zi_", "咨", "zi"),
    ("inspection_", "會勘通知單", "inspection"),
    ("phone_", "公務電話紀錄", "phone"),
    ("directive_", "手令", "directive"),
    ("shouling_", "手令", "directive"),
    ("memo_", "箋函", "memo"),
    ("jianjian_", "箋函", "memo"),
]


@dataclass
class ExampleRecord:
    doc_type: str
    source_file: str
    title: str
    sender: str
    receiver: str
    subject: str
    basis: str
    source_level: str
    user_input: str


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, flags=re.DOTALL)
    if not match:
        return {}, text
    meta_text, body = match.groups()
    try:
        metadata = yaml.safe_load(meta_text) or {}
    except yaml.YAMLError:
        metadata = {}
    return metadata, body


def _extract_bold_field(body: str, field: str) -> str:
    pattern = rf"\*\*{re.escape(field)}\*\*[：:]\s*(.+)"
    match = re.search(pattern, body)
    return match.group(1).strip() if match else ""


def _extract_section_line(body: str, heading: str) -> str:
    pattern = rf"###\s*{re.escape(heading)}\s*\n(.+?)(?:\n###|\n\*\*|$)"
    match = re.search(pattern, body, flags=re.DOTALL)
    if not match:
        return ""
    chunk = match.group(1).strip()
    for line in chunk.splitlines():
        stripped = line.strip()
        if stripped:
            return re.sub(r"^[一二三四五六七八九十]+、\s*", "", stripped)
    return ""


def _infer_doc_type(filename: str, metadata: dict[str, Any]) -> tuple[str, str]:
    meta_doc_type = str(metadata.get("doc_type", "")).strip()
    if meta_doc_type:
        for _, mapped_type, slug in _TYPE_PREFIX_MAP:
            if mapped_type == meta_doc_type:
                return mapped_type, slug
        return meta_doc_type, "other"

    lower = filename.lower()
    for prefix, mapped_type, slug in _TYPE_PREFIX_MAP:
        if lower.startswith(prefix):
            return mapped_type, slug
    return "未知", "other"


def _build_user_input(doc_type: str, sender: str, receiver: str, subject: str, basis: str) -> str:
    sender_txt = sender or "未指定機關"
    receiver_txt = receiver or "未指定受文者"
    subject_txt = subject or "未指定主旨"
    parts = [
        f"請撰寫一份{doc_type}。",
        f"發文機關：{sender_txt}。",
        f"受文者：{receiver_txt}。",
        f"主旨：{subject_txt}。",
    ]
    if basis:
        parts.append(f"請依據：{basis}。")
    return " ".join(parts)


def parse_example_file(path: Path) -> ExampleRecord:
    text = path.read_text(encoding="utf-8")
    metadata, body = _split_frontmatter(text)
    doc_type, _ = _infer_doc_type(path.name, metadata)

    sender = _extract_bold_field(body, "機關") or str(metadata.get("agency", "")).strip()
    receiver = _extract_bold_field(body, "受文者")
    subject = _extract_bold_field(body, "主旨") or _extract_section_line(body, "主旨")
    basis = _extract_bold_field(body, "依據") or _extract_section_line(body, "依據")
    title = str(metadata.get("title", "")).strip() or path.stem
    source_level = str(metadata.get("source_level", "")).strip()
    try:
        source_file = str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        source_file = str(path).replace("\\", "/")

    user_input = _build_user_input(doc_type, sender, receiver, subject, basis)

    return ExampleRecord(
        doc_type=doc_type,
        source_file=source_file,
        title=title,
        sender=sender,
        receiver=receiver,
        subject=subject,
        basis=basis,
        source_level=source_level,
        user_input=user_input,
    )


def _slug_for_doc_type(doc_type: str) -> str:
    for _, mapped_type, slug in _TYPE_PREFIX_MAP:
        if mapped_type == doc_type:
            return slug
    return "other"


def build_corpus(
    examples_dir: Path,
    doc_types: list[str],
    per_type: int,
) -> dict[str, Any]:
    by_type: dict[str, list[ExampleRecord]] = {doc_type: [] for doc_type in doc_types}
    for path in sorted(examples_dir.glob("*.md")):
        record = parse_example_file(path)
        if record.doc_type in by_type:
            by_type[record.doc_type].append(record)

    for doc_type in doc_types:
        found = len(by_type[doc_type])
        if found < per_type:
            raise ValueError(f"{doc_type} 樣本不足：需要 {per_type}，實際 {found}")

    items: list[dict[str, Any]] = []
    for doc_type in doc_types:
        slug = _slug_for_doc_type(doc_type)
        selected = by_type[doc_type][:per_type]
        for idx, rec in enumerate(selected, start=1):
            items.append({
                "id": f"{slug}-{idx:03d}",
                "doc_type": rec.doc_type,
                "title": rec.title,
                "source_file": rec.source_file,
                "user_input": rec.user_input,
                "reference": {
                    "sender": rec.sender,
                    "receiver": rec.receiver,
                    "subject": rec.subject,
                    "basis": rec.basis,
                    "source_level": rec.source_level,
                },
                "strict_request": dict(STRICT_REQUEST_DEFAULTS),
            })

    return {
        "name": f"mvp-benchmark-{len(items)}",
        "doc_types": doc_types,
        "per_type": per_type,
        "total_items": len(items),
        "strict_mode_defaults": dict(STRICT_REQUEST_DEFAULTS),
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="建置 benchmark 題庫（預設函/公告/簽各 10 題）")
    parser.add_argument("--examples-dir", type=Path, default=DEFAULT_EXAMPLES_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--per-type", type=int, default=10)
    parser.add_argument("--doc-type", action="append", dest="doc_types", default=[])
    args = parser.parse_args()

    doc_types = args.doc_types or list(DEFAULT_DOC_TYPES)
    if args.per_type <= 0:
        raise ValueError("--per-type 必須大於 0")

    corpus = build_corpus(args.examples_dir, doc_types, args.per_type)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(corpus, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[OK] 輸出題庫：{args.output}")
    print(f"[OK] 題數：{corpus['total_items']}（{', '.join(doc_types)} 各 {args.per_type}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
