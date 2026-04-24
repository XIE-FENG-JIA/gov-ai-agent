from pathlib import Path

from src.knowledge.corpus_provenance import is_active_corpus_metadata, is_fixture_backed_metadata

from ._shared import console
from .corpus import _load_full_document, _sanitize_metadata, parse_markdown_with_metadata


REBUILD_COLLECTIONS: tuple[tuple[str, str], ...] = (
    ("examples", "examples"),
    ("regulations", "regulations"),
    ("policies", "policies"),
)


def should_skip_rebuild_file(metadata: dict, only_real: bool) -> bool:
    if metadata.get("deprecated"):
        return True
    if not only_real:
        return False
    return not is_active_corpus_metadata(metadata)


def skip_reason(metadata: dict, only_real: bool) -> str | None:
    if metadata.get("deprecated"):
        return "deprecated"
    if not only_real:
        return None
    if is_active_corpus_metadata(metadata):
        return None
    if bool(metadata.get("synthetic")):
        return "synthetic"
    if is_fixture_backed_metadata(metadata):
        return "fixture_fallback"
    return "inactive"


def corpus_collection_for_metadata(metadata: dict) -> str:
    doc_type = str(metadata.get("doc_type", "")).strip()
    return "regulations" if doc_type == "法規" else "policies"


def print_provenance_summary(imported: int, skipped: dict[str, int]) -> None:
    details = [f"匯入 real {imported} 筆"]
    for reason in ("synthetic", "fixture_fallback", "deprecated", "inactive"):
        count = skipped.get(reason, 0)
        if count:
            details.append(f"跳過 {reason} {count} 筆")
    console.print(f"[bold cyan]only-real provenance：{' / '.join(details)}[/bold cyan]")


def rebuild_active_corpus(kb, corpus_root: Path) -> tuple[int, dict[str, int]]:
    files = sorted(corpus_root.rglob("*.md"))
    imported_by_collection = {collection: 0 for collection, _ in REBUILD_COLLECTIONS}
    skipped_by_reason: dict[str, int] = {}

    for file_idx, file_path in enumerate(files):
        metadata, content = parse_markdown_with_metadata(file_path)
        reason = skip_reason(metadata, only_real=True)
        if reason:
            skipped_by_reason[reason] = skipped_by_reason.get(reason, 0) + 1
            continue

        collection = corpus_collection_for_metadata(metadata)
        metadata.setdefault("title", file_path.stem)
        metadata.setdefault("doc_type", "unknown")
        doc_seed = str(metadata.get("source_id") or file_path.stem)
        saved_id = kb.upsert_document(
            kb.make_deterministic_id(doc_seed, collection),
            content,
            _sanitize_metadata(metadata),
            collection_name=collection,
            full_document=_load_full_document(kb, file_path, content),
            chunk_index=file_idx,
            total_chunks=len(files),
        )
        if saved_id:
            imported_by_collection[collection] += 1

    console.print(
        "[bold cyan]only-real 模式：以 active corpus 為唯一重建來源"
        f"（{corpus_root.as_posix()}）[/bold cyan]"
    )
    for collection, _ in REBUILD_COLLECTIONS:
        console.print(f"[green]{collection}[/green]：重建 {imported_by_collection[collection]} 筆")

    total_imported = sum(imported_by_collection.values())
    print_provenance_summary(total_imported, skipped_by_reason)
    return total_imported, skipped_by_reason
