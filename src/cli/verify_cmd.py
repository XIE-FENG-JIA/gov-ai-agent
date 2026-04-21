from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from src.document import read_docx_citation_metadata
from src.knowledge.corpus_provenance import is_active_corpus_metadata, read_markdown_frontmatter

console = Console()


def _load_corpus_entries(base_dir: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    if not base_dir.exists():
        return entries

    for path in sorted(base_dir.rglob("*.md")):
        try:
            meta, _ = read_markdown_frontmatter(path)
        except OSError:
            continue
        if not meta or not is_active_corpus_metadata(meta):
            continue
        entries.append(
            {
                "path": str(path),
                "title": str(meta.get("title") or ""),
                "source_id": str(meta.get("source_id") or meta.get("source_doc_no") or ""),
                "source_url": str(meta.get("source_url") or ""),
            }
        )
    return entries


def _find_corpus_match(source: dict, corpus_entries: list[dict[str, str]]) -> dict[str, str]:
    source_doc_id = str(source.get("source_doc_id") or "").strip()
    source_url = str(source.get("source_url") or "").strip()
    title = str(source.get("title") or "").strip()

    for entry in corpus_entries:
        if source_doc_id and source_doc_id == entry["source_id"]:
            return entry
    for entry in corpus_entries:
        if source_url and source_url == entry["source_url"]:
            return entry
    for entry in corpus_entries:
        if title and title == entry["title"]:
            return entry
    return {}


def verify(
    file_path: str = typer.Argument(..., help="要驗證 citation metadata 的 .docx 檔案"),
) -> None:
    docx_path = Path(file_path)
    if not docx_path.is_file():
        console.print(f"[red]錯誤：找不到檔案 {file_path}[/red]")
        raise typer.Exit(1)

    if docx_path.suffix.lower() != ".docx":
        console.print("[red]錯誤：僅支援 .docx 檔案格式。[/red]")
        raise typer.Exit(1)

    metadata = read_docx_citation_metadata(str(docx_path))
    if not metadata:
        console.print("[red]錯誤：文件缺少 citation metadata，無法驗證。[/red]")
        raise typer.Exit(1)

    citation_sources = list(metadata.get("citation_sources_json") or [])
    source_doc_ids = [str(item) for item in metadata.get("source_doc_ids") or []]
    citation_count = int(metadata.get("citation_count") or 0)

    corpus_entries = _load_corpus_entries(Path("kb_data") / "corpus")
    derived_ids = list(
        dict.fromkeys(
            str(source.get("source_doc_id") or "").strip()
            for source in citation_sources
            if str(source.get("source_doc_id") or "").strip()
        )
    )

    checks: list[tuple[str, bool, str]] = [
        ("metadata.citation_count", citation_count == len(citation_sources), f"{citation_count} vs {len(citation_sources)}"),
        ("metadata.source_doc_ids", source_doc_ids == derived_ids, f"{source_doc_ids}"),
        ("metadata.engine", bool(str(metadata.get("engine") or "").strip()), str(metadata.get("engine") or "")),
    ]

    for index, source in enumerate(citation_sources, start=1):
        match = _find_corpus_match(source, corpus_entries)
        label = str(source.get("source_doc_id") or source.get("title") or f"citation-{index}")
        if match:
            checks.append((f"citation[{index}] {label}", True, match["path"]))
        else:
            checks.append((f"citation[{index}] {label}", False, "找不到對應 repo evidence"))

    table = Table(title="Citation 驗證結果", show_lines=True)
    table.add_column("檢查項目", style="cyan", width=30)
    table.add_column("狀態", width=6, justify="center")
    table.add_column("說明", width=60)

    passed = 0
    for name, ok, detail in checks:
        if ok:
            passed += 1
        table.add_row(name, "[green]PASS[/green]" if ok else "[red]FAIL[/red]", detail)

    console.print(table)
    console.print(f"\n  通過：{passed}/{len(checks)} 項")

    if passed != len(checks):
        raise typer.Exit(1)
