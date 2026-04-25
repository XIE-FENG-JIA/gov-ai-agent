import datetime
import json
from pathlib import Path
from typing import Any

import yaml
import typer
from rich.table import Table

from ._shared import app, console, logger


def parse_markdown_with_metadata(file_path: Path) -> tuple[dict[str, Any], str]:
    """解析含有 YAML frontmatter 的 Markdown 檔案。"""
    content = file_path.read_text(encoding="utf-8")
    if content.startswith("---"):
        try:
            parts = content.split("---", 2)
            if len(parts) >= 3:
                metadata = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip()
                return metadata, body
        except (yaml.YAMLError, ValueError) as exc:
            console.print(f"[yellow]解析 {file_path.name} 時發生警告：{exc}[/yellow]")
    return {}, content


def _sanitize_metadata(metadata: dict) -> dict:
    """清理 metadata 使其相容於 ChromaDB（僅允許 str/int/float/bool）。"""
    clean: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, (datetime.date, datetime.datetime)):
            clean[key] = value.isoformat()
        elif isinstance(value, list):
            clean[key] = json.dumps(value, ensure_ascii=False)
        elif value is None:
            continue
        elif isinstance(value, (str, int, float, bool)):
            clean[key] = value
        else:
            clean[key] = str(value)
    return clean


def _init_kb():
    """初始化 ConfigManager → LLM → KnowledgeBaseManager 的共用邏輯。"""
    from . import ConfigManager, KnowledgeBaseManager, get_llm_factory

    config_manager = ConfigManager()
    config = config_manager.config
    llm_config = config.get("llm")
    if not llm_config:
        console.print("[red]錯誤：設定檔缺少 'llm' 區塊，請檢查 config.yaml[/red]")
        raise typer.Exit(1)
    llm = get_llm_factory(llm_config, full_config=config)
    kb_path = config.get("knowledge_base", {}).get("path", "./kb_data")
    contextual_retrieval = config.get("knowledge_base", {}).get("contextual_retrieval", False)
    return KnowledgeBaseManager(
        persist_path=kb_path,
        llm_provider=llm,
        contextual_retrieval=bool(contextual_retrieval),
    )


def _load_full_document(kb, file_path: Path, content: str) -> str | None:
    if not kb.contextual_retrieval:
        return None
    try:
        return file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("讀取完整文件 %s 失敗，使用片段 fallback：%s", file_path, exc)
        return content


@app.command()
def ingest(
    source_dir: str = typer.Option("./kb_data/examples", help="要匯入的 Markdown 檔案所在目錄"),
    collection: str = typer.Option(
        "examples",
        "--collection",
        "-c",
        help="目標集合（examples/regulations/policies）",
    ),
    reset: bool = typer.Option(False, help="匯入前重設資料庫（注意：將清除所有已匯入的資料）"),
) -> None:
    """
    將 Markdown 檔案匯入知識庫。

    範例：

        gov-ai kb ingest

        gov-ai kb ingest --source-dir ./my_docs

        gov-ai kb ingest -c regulations --reset
    """
    from . import _init_kb as init_kb

    kb = init_kb()
    if reset:
        console.print("[bold red]正在重設知識庫...[/bold red]")
        kb.reset_db()

    source_path = Path(source_dir)
    if not source_path.exists():
        console.print(f"[red]找不到來源目錄：{source_dir}[/red]")
        raise typer.Exit(1)

    files = list(source_path.glob("*.md"))
    console.print(f"在 {source_dir} 中找到 {len(files)} 個 Markdown 檔案")

    if kb.contextual_retrieval:
        console.print("[bold cyan][Contextual Retrieval] 已啟用，正在為 chunk 加入上下文...[/bold cyan]")
        console.print("[dim]每個 chunk 會透過 LLM 生成上下文摘要前綴，匯入速度可能較慢。[/dim]")

    success_count = 0
    deprecated_count = 0
    failed_count = 0
    with typer.progressbar(files, label=f"正在匯入至 '{collection}'") as progress:
        for file_idx, file_path in enumerate(progress):
            metadata, content = parse_markdown_with_metadata(file_path)
            if metadata.get("deprecated"):
                console.print(f"[yellow]跳過已棄用檔案：{file_path.name}[/yellow]")
                deprecated_count += 1
                continue

            metadata.setdefault("title", file_path.stem)
            metadata.setdefault("doc_type", "unknown")

            doc_id = kb.upsert_document(
                kb.make_deterministic_id(file_path.stem, collection),
                content,
                _sanitize_metadata(metadata),
                collection_name=collection,
                full_document=_load_full_document(kb, file_path, content),
                chunk_index=file_idx,
                total_chunks=len(files),
            )
            if doc_id:
                success_count += 1
            else:
                failed_count += 1

    if deprecated_count > 0:
        console.print(f"[yellow]已跳過 {deprecated_count} 筆已棄用文件。[/yellow]")
    if failed_count > 0:
        console.print(
            f"[bold red]警告：{failed_count} 筆文件因 embedding 產生失敗而未匯入。"
            "請確認 Embedding 服務已啟動（如 Ollama）。[/bold red]"
        )
    console.print(f"[green]成功匯入（upsert）{success_count} 筆文件至 '{collection}'！[/green]")
    console.print(f"目前資料庫統計：{kb.get_stats()}")


@app.command()
def sync(
    source_dir: str = typer.Option("./kb_data/examples", help="要掃描的 Markdown 檔案目錄"),
    collection: str = typer.Option(
        "examples",
        "--collection",
        "-c",
        help="目標集合（examples/regulations/policies）",
    ),
) -> None:
    """增量同步知識庫——只匯入尚未索引的新檔案。"""
    from . import _init_kb as init_kb

    kb = init_kb()
    source_path = Path(source_dir)
    if not source_path.exists():
        console.print(f"[red]找不到來源目錄：{source_dir}[/red]")
        raise typer.Exit(1)

    files = list(source_path.glob("*.md"))
    console.print(f"掃描 {source_dir}：找到 {len(files)} 個 Markdown 檔案")

    new_count = 0
    skipped_count = 0
    deprecated_count = 0
    failed_count = 0

    for file_idx, file_path in enumerate(files):
        metadata, content = parse_markdown_with_metadata(file_path)
        if metadata.get("deprecated"):
            deprecated_count += 1
            continue

        metadata.setdefault("title", file_path.stem)
        metadata.setdefault("doc_type", "unknown")
        doc_id = kb.make_deterministic_id(file_path.stem, collection)
        if kb.document_exists(doc_id, collection):
            skipped_count += 1
            continue

        saved_id = kb.upsert_document(
            doc_id,
            content,
            _sanitize_metadata(metadata),
            collection_name=collection,
            full_document=_load_full_document(kb, file_path, content),
            chunk_index=file_idx,
            total_chunks=len(files),
        )
        if saved_id:
            new_count += 1
            console.print(f"  [green]+[/green] {file_path.name}")
        else:
            failed_count += 1
            console.print(f"  [red]✗[/red] {file_path.name} （embedding 失敗）")

    console.print("")
    console.print(
        f"[bold]同步完成：[/bold] {new_count} 新增 / {skipped_count} 已索引（略過）"
        + (f" / {deprecated_count} 已棄用" if deprecated_count else "")
        + (f" / [red]{failed_count} 失敗[/red]" if failed_count else "")
    )
    if new_count == 0 and failed_count == 0:
        console.print("[dim]知識庫已是最新狀態，無需更新。[/dim]")
    console.print(f"目前資料庫統計：{kb.get_stats()}")


@app.command()
def search(
    query: str = typer.Argument(..., help="搜尋關鍵字（語意搜尋，不限完全匹配）"),
    limit: int = typer.Option(3, "--limit", "-n", help="回傳結果數量", min=1, max=100),
) -> None:
    """在知識庫中搜尋相關文件（語意搜尋）。"""
    if not query.strip():
        console.print("[red]錯誤：搜尋關鍵字不可為空白。[/red]")
        raise typer.Exit(1)

    from . import _init_kb as init_kb

    kb = init_kb()
    if not kb.is_available:
        console.print("[red]錯誤：知識庫初始化失敗，無法搜尋。[/red]")
        console.print("[dim]提示：請確認知識庫路徑正確，並嘗試 'gov-ai kb ingest' 重新匯入。[/dim]")
        raise typer.Exit(1)

    console.print(f"正在搜尋：[bold cyan]{query}[/bold cyan]...")
    results = kb.search_hybrid(query, n_results=limit)
    if not results:
        console.print("[yellow]找不到符合的文件。[/yellow]")
        console.print("[dim]提示：知識庫可能尚無資料，請先執行 'gov-ai kb ingest' 或 'gov-ai kb fetch-laws --ingest'。[/dim]")
        return

    table = Table(title=f"搜尋結果（前 {len(results)} 筆）", show_lines=True)
    table.add_column("相似度", style="magenta", no_wrap=True, width=7)
    table.add_column("等級", style="bold", no_wrap=True, width=5)
    table.add_column("類型", style="cyan", width=8)
    table.add_column("標題", style="green")
    table.add_column("摘要", max_width=60)
    for result in results:
        metadata = result.get("metadata", {})
        content = result.get("content", "")
        level = metadata.get("source_level", "B") if isinstance(metadata, dict) else "B"
        table.add_row(
            f"{1 - result.get('distance', 0):.2f}" if result.get("distance") is not None else "N/A",
            "[green]A[/green]" if level == "A" else "[dim]B[/dim]",
            metadata.get("doc_type", "未知") if isinstance(metadata, dict) else "未知",
            metadata.get("title", "無標題") if isinstance(metadata, dict) else "無標題",
            content[:100].replace("\n", " ") + "..." if content else "（無內容）",
        )
    console.print(table)


def _ingest_fetch_results(results: list, kb) -> int:
    """將 FetchResult 清單匯入知識庫，回傳成功筆數。"""
    if kb.contextual_retrieval:
        console.print("[bold cyan][Contextual Retrieval] 已啟用，匯入時將為 chunk 加入上下文...[/bold cyan]")
    total = len(results)
    success = 0
    for idx, result in enumerate(results):
        metadata, content = parse_markdown_with_metadata(result.file_path)
        if kb.add_document(
            content,
            _sanitize_metadata(metadata),
            collection_name=result.collection,
            full_document=_load_full_document(kb, result.file_path, content),
            chunk_index=idx,
            total_chunks=total,
        ):
            success += 1
    return success
