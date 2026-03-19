import datetime
import json
import os
import typer
from pathlib import Path
from typing import Any
from rich.console import Console
from rich.table import Table
from src.core.config import ConfigManager
from src.core.llm import get_llm_factory
from src.knowledge.manager import KnowledgeBaseManager

console = Console()
app = typer.Typer()


def parse_markdown_with_metadata(file_path: Path) -> tuple[dict[str, Any], str]:
    """解析含有 YAML frontmatter 的 Markdown 檔案。"""
    content = file_path.read_text(encoding='utf-8')
    if content.startswith('---'):
        try:
            parts = content.split('---', 2)
            if len(parts) >= 3:
                import yaml
                metadata = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip()
                return metadata, body
        except Exception as e:
            console.print(f"[yellow]解析 {file_path.name} 時發生警告：{e}[/yellow]")

    # Fallback
    return {}, content


def _sanitize_metadata(metadata: dict) -> dict:
    """清理 metadata 使其相容於 ChromaDB（僅允許 str/int/float/bool）。"""
    clean: dict[str, Any] = {}
    for k, v in metadata.items():
        if isinstance(v, (datetime.date, datetime.datetime)):
            clean[k] = v.isoformat()
        elif isinstance(v, list):
            clean[k] = json.dumps(v, ensure_ascii=False)
        elif v is None:
            pass  # ChromaDB 不接受 None 值，略過
        elif isinstance(v, (str, int, float, bool)):
            clean[k] = v
        else:
            clean[k] = str(v)
    return clean


def _init_kb() -> KnowledgeBaseManager:
    """初始化 ConfigManager → LLM → KnowledgeBaseManager 的共用邏輯。"""
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


@app.command()
def ingest(
    source_dir: str = typer.Option("./kb_data/examples", help="要匯入的 Markdown 檔案所在目錄"),
    collection: str = typer.Option("examples", "--collection", "-c", help="目標集合（examples/regulations/policies）"),
    reset: bool = typer.Option(False, help="匯入前重設資料庫（注意：將清除所有已匯入的資料）")
) -> None:
    """
    將 Markdown 檔案匯入知識庫。

    範例：

        gov-ai kb ingest                          匯入預設範例目錄

        gov-ai kb ingest --source-dir ./my_docs   匯入自訂目錄

        gov-ai kb ingest -c regulations --reset   重設後匯入法規
    """
    kb = _init_kb()

    if reset:
        console.print("[bold red]正在重設知識庫...[/bold red]")
        kb.reset_db()

    source_path = Path(source_dir)
    if not source_path.exists():
        console.print(f"[red]找不到來源目錄：{source_dir}[/red]")
        raise typer.Exit(1)

    files = list(source_path.glob("*.md"))
    console.print(f"在 {source_dir} 中找到 {len(files)} 個 Markdown 檔案")

    # Contextual Retrieval 提示
    if kb.contextual_retrieval:
        console.print(
            "[bold cyan][Contextual Retrieval] 已啟用，正在為 chunk 加入上下文...[/bold cyan]"
        )
        console.print(
            "[dim]每個 chunk 會透過 LLM 生成上下文摘要前綴，匯入速度可能較慢。[/dim]"
        )

    success_count = 0
    deprecated_count = 0
    failed_count = 0
    with typer.progressbar(files, label=f"正在匯入至 '{collection}'") as progress:
        for file_idx, file_path in enumerate(progress):
            metadata, content = parse_markdown_with_metadata(file_path)

            # 跳過已棄用的文件
            if metadata.get("deprecated"):
                console.print(f"[yellow]跳過已棄用檔案：{file_path.name}[/yellow]")
                deprecated_count += 1
                continue

            # Ensure essential metadata
            if "title" not in metadata:
                metadata["title"] = file_path.stem
            if "doc_type" not in metadata:
                metadata["doc_type"] = "unknown"

            clean_metadata = _sanitize_metadata(metadata)

            # 讀取完整文件內容供 Contextual Retrieval 使用
            full_doc_content: str | None = None
            if kb.contextual_retrieval:
                try:
                    full_doc_content = file_path.read_text(encoding="utf-8")
                except Exception:
                    full_doc_content = content  # fallback

            doc_id = kb.add_document(
                content,
                clean_metadata,
                collection_name=collection,
                full_document=full_doc_content,
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
    console.print(f"[green]成功匯入 {success_count} 筆文件至 '{collection}'！[/green]")
    stats = kb.get_stats()
    console.print(f"目前資料庫統計：{stats}")


@app.command()
def search(
    query: str = typer.Argument(..., help="搜尋關鍵字（語意搜尋，不限完全匹配）"),
    limit: int = typer.Option(3, "--limit", "-n", help="回傳結果數量", min=1, max=100)
) -> None:
    """
    在知識庫中搜尋相關文件（語意搜尋）。

    範例：

        gov-ai kb search "資源回收"

        gov-ai kb search "勞動基準法" -n 10
    """
    if not query.strip():
        console.print("[red]錯誤：搜尋關鍵字不可為空白。[/red]")
        raise typer.Exit(1)

    kb = _init_kb()

    if not kb.is_available:
        console.print("[red]錯誤：知識庫初始化失敗，無法搜尋。[/red]")
        console.print("[dim]提示：請確認知識庫路徑正確，並嘗試 'gov-ai kb ingest' 重新匯入。[/dim]")
        raise typer.Exit(1)

    console.print(f"正在搜尋：[bold cyan]{query}[/bold cyan]...")
    results = kb.search_hybrid(query, n_results=limit)

    if not results:
        console.print("[yellow]找不到符合的文件。[/yellow]")
        console.print(
            "[dim]提示：知識庫可能尚無資料，請先執行 "
            "'gov-ai kb ingest' 或 'gov-ai kb fetch-laws --ingest'。[/dim]"
        )
        return

    table = Table(title=f"搜尋結果（前 {len(results)} 筆）", show_lines=True)
    table.add_column("相似度", style="magenta", no_wrap=True, width=7)
    table.add_column("等級", style="bold", no_wrap=True, width=5)
    table.add_column("類型", style="cyan", width=8)
    table.add_column("標題", style="green")
    table.add_column("摘要", max_width=60)

    for res in results:
        distance = res.get("distance", 0)
        score = f"{1 - distance:.2f}" if distance is not None else "N/A"  # 餘弦距離 -> 相似度
        metadata = res.get("metadata", {})
        content = res.get("content", "")
        excerpt = content[:100].replace('\n', ' ') + "..." if content else "（無內容）"

        level = metadata.get("source_level", "B") if isinstance(metadata, dict) else "B"
        level_display = "[green]A[/green]" if level == "A" else "[dim]B[/dim]"

        table.add_row(
            score,
            level_display,
            metadata.get("doc_type", "未知") if isinstance(metadata, dict) else "未知",
            metadata.get("title", "無標題") if isinstance(metadata, dict) else "無標題",
            excerpt
        )

    console.print(table)


# ========== 政府 API 擷取命令 ==========

def _ingest_fetch_results(results: list, kb: KnowledgeBaseManager) -> int:
    """將 FetchResult 清單匯入知識庫，回傳成功筆數。"""
    if kb.contextual_retrieval:
        console.print(
            "[bold cyan][Contextual Retrieval] 已啟用，匯入時將為 chunk 加入上下文...[/bold cyan]"
        )
    total = len(results)
    success = 0
    for idx, r in enumerate(results):
        metadata, content = parse_markdown_with_metadata(r.file_path)
        clean = _sanitize_metadata(metadata)

        # 讀取完整文件供 Contextual Retrieval 使用
        full_doc: str | None = None
        if kb.contextual_retrieval:
            try:
                full_doc = r.file_path.read_text(encoding="utf-8")
            except Exception:
                full_doc = content

        if kb.add_document(
            content,
            clean,
            collection_name=r.collection,
            full_document=full_doc,
            chunk_index=idx,
            total_chunks=total,
        ):
            success += 1
    return success


@app.command("fetch-laws")
def fetch_laws(
    output_dir: str = typer.Option(
        "./kb_data/regulations/laws",
        help="輸出目錄",
    ),
    laws: str = typer.Option(
        "",
        help="指定法規 PCode（逗號分隔），空白則使用預設清單",
    ),
    do_ingest: bool = typer.Option(
        False,
        "--ingest",
        "-I",
        help="擷取後自動匯入知識庫",
    ),
    bulk: bool = typer.Option(
        False,
        "--bulk",
        help="使用 bulk XML 下載模式（全量下載）",
    ),
) -> None:
    """
    從全國法規資料庫擷取法規全文（Level A 來源）。

    範例：

        gov-ai kb fetch-laws --ingest            擷取預設法規並匯入

        gov-ai kb fetch-laws --laws "A0030055"   擷取指定法規

        gov-ai kb fetch-laws --bulk              使用 bulk XML 全量下載
    """
    from src.knowledge.fetchers.law_fetcher import LawFetcher
    from src.knowledge.fetchers.constants import DEFAULT_LAW_PCODES

    pcodes = DEFAULT_LAW_PCODES
    if laws.strip():
        codes = [c.strip() for c in laws.split(",") if c.strip()]
        pcodes = {c: DEFAULT_LAW_PCODES.get(c, c) for c in codes}

    fetcher = LawFetcher(output_dir=Path(output_dir), pcodes=pcodes)

    if bulk:
        console.print(f"[bold]正在從{fetcher.name()} bulk 下載全量法規...[/bold]")
        results = fetcher.fetch_bulk()
    else:
        console.print(f"[bold]正在從{fetcher.name()}擷取 {len(pcodes)} 部法規...[/bold]")
        results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")

    if do_ingest and results:
        kb = _init_kb()
        count = _ingest_fetch_results(results, kb)
        console.print(f"[green]已匯入 {count} 筆至知識庫[/green]")
        console.print(f"目前資料庫統計：{kb.get_stats()}")


@app.command("fetch-gazette")
def fetch_gazette(
    output_dir: str = typer.Option(
        "./kb_data/examples/gazette",
        help="輸出目錄",
    ),
    days: int = typer.Option(7, help="擷取最近 N 天的公報"),
    category: str = typer.Option("", help="篩選特定類別（如：法規命令）"),
    do_ingest: bool = typer.Option(
        False,
        "--ingest",
        "-I",
        help="擷取後自動匯入知識庫",
    ),
    bulk: bool = typer.Option(
        False,
        "--bulk",
        help="使用 bulk ZIP 下載模式（含 PDF）",
    ),
    no_pdf: bool = typer.Option(
        False,
        "--no-pdf",
        help="bulk 模式下跳過 PDF 全文提取",
    ),
) -> None:
    """
    從行政院公報擷取近期公報（Level A 來源）。

    範例：

        gov-ai kb fetch-gazette --ingest               擷取近 7 天公報並匯入

        gov-ai kb fetch-gazette --days 30 --ingest      擷取近 30 天公報

        gov-ai kb fetch-gazette --category "法規命令"    篩選特定類別

        gov-ai kb fetch-gazette --bulk                  使用 bulk ZIP 下載（含 PDF）

        gov-ai kb fetch-gazette --bulk --no-pdf         bulk 下載但跳過 PDF
    """
    from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

    fetcher = GazetteFetcher(
        output_dir=Path(output_dir),
        days=days,
        category_filter=category if category.strip() else None,
    )

    if bulk:
        console.print(f"[bold]正在從{fetcher.name()} bulk 下載公報 ZIP...[/bold]")
        results = fetcher.fetch_bulk(extract_pdf=not no_pdf)
    else:
        console.print(f"[bold]正在從{fetcher.name()}擷取最近 {days} 天的公報...[/bold]")
        results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")

    if do_ingest and results:
        kb = _init_kb()
        count = _ingest_fetch_results(results, kb)
        console.print(f"[green]已匯入 {count} 筆至知識庫[/green]")
        console.print(f"目前資料庫統計：{kb.get_stats()}")


@app.command("fetch-opendata")
def fetch_opendata(
    output_dir: str = typer.Option(
        "./kb_data/policies/opendata",
        help="輸出目錄",
    ),
    keyword: str = typer.Option("警政署", help="搜尋關鍵字"),
    limit: int = typer.Option(10, help="最大資料集數量"),
    do_ingest: bool = typer.Option(
        False,
        "--ingest",
        "-I",
        help="擷取後自動匯入知識庫",
    ),
) -> None:
    """
    從政府資料開放平臺搜尋資料集（Level B 來源）。

    範例：

        gov-ai kb fetch-opendata --ingest                     搜尋預設關鍵字並匯入

        gov-ai kb fetch-opendata --keyword "環保" --limit 20  搜尋環保相關資料集
    """
    from src.knowledge.fetchers.opendata_fetcher import OpenDataFetcher

    fetcher = OpenDataFetcher(
        output_dir=Path(output_dir),
        keyword=keyword,
        limit=limit,
    )
    console.print(f"[bold]正在從{fetcher.name()}搜尋「{keyword}」...[/bold]")

    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")

    if do_ingest and results:
        kb = _init_kb()
        count = _ingest_fetch_results(results, kb)
        console.print(f"[green]已匯入 {count} 筆至知識庫[/green]")
        console.print(f"目前資料庫統計：{kb.get_stats()}")


@app.command("list")
def list_kb() -> None:
    """
    列出知識庫統計資訊和各集合的文件數量。

    範例：

        gov-ai kb list
    """
    kb = _init_kb()

    if not kb.is_available:
        console.print("[red]錯誤：知識庫不可用。[/red]")
        console.print("[dim]提示：請確認知識庫路徑正確，並嘗試 'gov-ai kb ingest' 匯入資料。[/dim]")
        raise typer.Exit(1)

    stats = kb.get_stats()

    table = Table(title="知識庫統計", show_lines=True)
    table.add_column("集合名稱", style="cyan", no_wrap=True)
    table.add_column("文件數量", style="magenta", justify="right")
    table.add_column("說明", style="dim")

    table.add_row(
        "examples",
        str(stats.get("examples_count", 0)),
        "公文範例（函、公告、簽等）"
    )
    table.add_row(
        "regulations",
        str(stats.get("regulations_count", 0)),
        "法規文件（Level A 權威來源）"
    )
    table.add_row(
        "policies",
        str(stats.get("policies_count", 0)),
        "政策文件（Level B 輔助來源）"
    )

    total = sum(stats.values())
    table.add_row(
        "[bold]合計[/bold]",
        f"[bold]{total}[/bold]",
        ""
    )

    console.print(table)

    if total == 0:
        console.print("\n[yellow]知識庫目前為空。[/yellow]")
        console.print("[dim]建議執行以下命令匯入資料：[/dim]")
        console.print("[dim]  gov-ai kb ingest                   匯入本地範例[/dim]")
        console.print("[dim]  gov-ai kb fetch-laws --ingest      匯入法規[/dim]")
        console.print("[dim]  gov-ai kb fetch-gazette --ingest   匯入公報[/dim]")


@app.command("fetch-npa")
def fetch_npa(
    output_dir: str = typer.Option(
        "./kb_data/policies/npa",
        help="輸出目錄",
    ),
    do_ingest: bool = typer.Option(
        False,
        "--ingest",
        "-I",
        help="擷取後自動匯入知識庫",
    ),
) -> None:
    """
    從警政署 OPEN DATA 擷取警政資料集（Level B 來源）。

    範例：

        gov-ai kb fetch-npa --ingest    擷取警政署資料並匯入
    """
    from src.knowledge.fetchers.npa_fetcher import NpaFetcher

    fetcher = NpaFetcher(output_dir=Path(output_dir))
    console.print(f"[bold]正在從{fetcher.name()}擷取資料...[/bold]")

    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")

    if do_ingest and results:
        kb = _init_kb()
        count = _ingest_fetch_results(results, kb)
        console.print(f"[green]已匯入 {count} 筆至知識庫[/green]")
        console.print(f"目前資料庫統計：{kb.get_stats()}")


@app.command("fetch-legislative")
def fetch_legislative(
    output_dir: str = typer.Option(
        "./kb_data/policies/legislative",
        help="輸出目錄",
    ),
    term: str = typer.Option("all", help="屆期（如 11），預設 all"),
    limit: int = typer.Option(50, help="最大議案數量"),
    do_ingest: bool = typer.Option(
        False, "--ingest", "-I", help="擷取後自動匯入知識庫",
    ),
) -> None:
    """
    從立法院開放資料擷取議案（Level B 來源）。

    範例：

        gov-ai kb fetch-legislative --term 11 --limit 50 --ingest
    """
    from src.knowledge.fetchers.legislative_fetcher import LegislativeFetcher

    fetcher = LegislativeFetcher(output_dir=Path(output_dir), term=term, limit=limit)
    console.print(f"[bold]正在從{fetcher.name()}擷取資料...[/bold]")
    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")

    if do_ingest and results:
        kb = _init_kb()
        count = _ingest_fetch_results(results, kb)
        console.print(f"[green]已匯入 {count} 筆至知識庫[/green]")
        console.print(f"目前資料庫統計：{kb.get_stats()}")


@app.command("fetch-debates")
def fetch_debates(
    output_dir: str = typer.Option(
        "./kb_data/policies/legislative_debates",
        help="輸出目錄",
    ),
    limit: int = typer.Option(30, help="最大質詢紀錄數量"),
    do_ingest: bool = typer.Option(
        False, "--ingest", "-I", help="擷取後自動匯入知識庫",
    ),
) -> None:
    """
    從立法院 g0v API 擷取質詢與會議紀錄（Level B 來源）。

    範例：

        gov-ai kb fetch-debates --limit 30 --ingest
    """
    from src.knowledge.fetchers.legislative_debate_fetcher import LegislativeDebateFetcher

    fetcher = LegislativeDebateFetcher(output_dir=Path(output_dir), limit=limit)
    console.print(f"[bold]正在從{fetcher.name()}擷取資料...[/bold]")
    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")

    if do_ingest and results:
        kb = _init_kb()
        count = _ingest_fetch_results(results, kb)
        console.print(f"[green]已匯入 {count} 筆至知識庫[/green]")
        console.print(f"目前資料庫統計：{kb.get_stats()}")


@app.command("fetch-procurement")
def fetch_procurement(
    output_dir: str = typer.Option(
        "./kb_data/policies/procurement",
        help="輸出目錄",
    ),
    days: int = typer.Option(7, help="擷取最近 N 天的採購公告"),
    limit: int = typer.Option(50, help="最大公告數量"),
    keyword: str = typer.Option("", help="搜尋關鍵字（空白則依日期列出）"),
    do_ingest: bool = typer.Option(
        False, "--ingest", "-I", help="擷取後自動匯入知識庫",
    ),
) -> None:
    """
    從 g0v 採購 API 擷取政府採購公告（Level B 來源）。

    範例：

        gov-ai kb fetch-procurement --days 7 --limit 50 --ingest

        gov-ai kb fetch-procurement --keyword "資訊系統" --limit 20
    """
    from src.knowledge.fetchers.procurement_fetcher import ProcurementFetcher

    fetcher = ProcurementFetcher(output_dir=Path(output_dir), days=days, limit=limit, keyword=keyword)
    console.print(f"[bold]正在從{fetcher.name()}擷取資料...[/bold]")
    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")

    if do_ingest and results:
        kb = _init_kb()
        count = _ingest_fetch_results(results, kb)
        console.print(f"[green]已匯入 {count} 筆至知識庫[/green]")
        console.print(f"目前資料庫統計：{kb.get_stats()}")


@app.command("fetch-judicial")
def fetch_judicial(
    output_dir: str = typer.Option(
        "./kb_data/regulations/judicial",
        help="輸出目錄",
    ),
    limit: int = typer.Option(20, help="最大裁判書數量"),
    do_ingest: bool = typer.Option(
        False, "--ingest", "-I", help="擷取後自動匯入知識庫",
    ),
) -> None:
    """
    從司法院裁判書 API 擷取裁判書全文（Level A 來源，需設定環境變數）。

    需要環境變數：JUDICIAL_USER、JUDICIAL_PASSWORD

    範例：

        gov-ai kb fetch-judicial --limit 20 --ingest
    """
    from src.knowledge.fetchers.judicial_fetcher import JudicialFetcher

    fetcher = JudicialFetcher(output_dir=Path(output_dir), limit=limit)
    console.print(f"[bold]正在從{fetcher.name()}擷取資料...[/bold]")
    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")

    if do_ingest and results:
        kb = _init_kb()
        count = _ingest_fetch_results(results, kb)
        console.print(f"[green]已匯入 {count} 筆至知識庫[/green]")
        console.print(f"目前資料庫統計：{kb.get_stats()}")



@app.command("fetch-interpretations")
def fetch_interpretations(
    output_dir: str = typer.Option(
        "./kb_data/regulations/interpretations",
        help="輸出目錄",
    ),
    limit: int = typer.Option(30, help="最大函釋數量"),
    keyword: str = typer.Option("", help="搜尋關鍵字（可選）"),
    do_ingest: bool = typer.Option(
        False, "--ingest", "-I", help="擷取後自動匯入知識庫",
    ),
) -> None:
    """
    從法務部主管法規查詢系統擷取行政函釋（Level A 來源）。

    範例：

        gov-ai kb fetch-interpretations --limit 30 --ingest

        gov-ai kb fetch-interpretations --keyword "行政程序" --ingest
    """
    from src.knowledge.fetchers.interpretation_fetcher import InterpretationFetcher

    fetcher = InterpretationFetcher(output_dir=Path(output_dir), limit=limit, keyword=keyword)
    console.print(f"[bold]正在從{fetcher.name()}擷取資料...[/bold]")
    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")

    if do_ingest and results:
        kb = _init_kb()
        count = _ingest_fetch_results(results, kb)
        console.print(f"[green]已匯入 {count} 筆至知識庫[/green]")
        console.print(f"目前資料庫統計：{kb.get_stats()}")


@app.command("fetch-local")
def fetch_local(
    output_dir: str = typer.Option(
        "./kb_data/regulations/local",
        help="輸出目錄",
    ),
    city: str = typer.Option("taipei", help="城市代碼（如 taipei）"),
    limit: int = typer.Option(30, help="最大法規數量"),
    do_ingest: bool = typer.Option(
        False, "--ingest", "-I", help="擷取後自動匯入知識庫",
    ),
) -> None:
    """
    從地方法規查詢系統擷取地方自治法規（Level A 來源）。

    範例：

        gov-ai kb fetch-local --city taipei --limit 30 --ingest
    """
    from src.knowledge.fetchers.local_regulation_fetcher import LocalRegulationFetcher

    fetcher = LocalRegulationFetcher(output_dir=Path(output_dir), city=city, limit=limit)
    console.print(f"[bold]正在從{fetcher.name()}擷取資料...[/bold]")
    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")

    if do_ingest and results:
        kb = _init_kb()
        count = _ingest_fetch_results(results, kb)
        console.print(f"[green]已匯入 {count} 筆至知識庫[/green]")
        console.print(f"目前資料庫統計：{kb.get_stats()}")


@app.command("fetch-examyuan")
def fetch_examyuan(
    output_dir: str = typer.Option(
        "./kb_data/regulations/exam_yuan",
        help="輸出目錄",
    ),
    limit: int = typer.Option(30, help="最大法規數量"),
    do_ingest: bool = typer.Option(
        False, "--ingest", "-I", help="擷取後自動匯入知識庫",
    ),
) -> None:
    """
    從考試院法規資料庫擷取人事法規（Level B 來源）。

    範例：

        gov-ai kb fetch-examyuan --limit 30 --ingest
    """
    from src.knowledge.fetchers.exam_yuan_fetcher import ExamYuanFetcher

    fetcher = ExamYuanFetcher(output_dir=Path(output_dir), limit=limit)
    console.print(f"[bold]正在從{fetcher.name()}擷取資料...[/bold]")
    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")

    if do_ingest and results:
        kb = _init_kb()
        count = _ingest_fetch_results(results, kb)
        console.print(f"[green]已匯入 {count} 筆至知識庫[/green]")
        console.print(f"目前資料庫統計：{kb.get_stats()}")


@app.command("fetch-statistics")
def fetch_statistics(
    output_dir: str = typer.Option(
        "./kb_data/policies/statistics",
        help="輸出目錄",
    ),
    limit: int = typer.Option(10, help="最大統計通報數量"),
    do_ingest: bool = typer.Option(
        False, "--ingest", "-I", help="擷取後自動匯入知識庫",
    ),
) -> None:
    """
    從主計總處統計發布訊息擷取統計通報（Level B 來源）。

    範例：

        gov-ai kb fetch-statistics --limit 10 --ingest
    """
    from src.knowledge.fetchers.statistics_fetcher import StatisticsFetcher

    fetcher = StatisticsFetcher(output_dir=Path(output_dir), limit=limit)
    console.print(f"[bold]正在從{fetcher.name()}擷取資料...[/bold]")
    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")

    if do_ingest and results:
        kb = _init_kb()
        count = _ingest_fetch_results(results, kb)
        console.print(f"[green]已匯入 {count} 筆至知識庫[/green]")
        console.print(f"目前資料庫統計：{kb.get_stats()}")


@app.command("fetch-controlyuan")
def fetch_controlyuan(
    output_dir: str = typer.Option(
        "./kb_data/policies/control_yuan",
        help="輸出目錄",
    ),
    limit: int = typer.Option(20, help="最大糾正案數量"),
    do_ingest: bool = typer.Option(
        False, "--ingest", "-I", help="擷取後自動匯入知識庫",
    ),
) -> None:
    """
    從監察院擷取糾正案文（Level A 來源）。

    範例：

        gov-ai kb fetch-controlyuan --limit 20 --ingest
    """
    from src.knowledge.fetchers.control_yuan_fetcher import ControlYuanFetcher

    fetcher = ControlYuanFetcher(output_dir=Path(output_dir), limit=limit)
    console.print(f"[bold]正在從{fetcher.name()}擷取資料...[/bold]")
    results = fetcher.fetch()
    console.print(f"[green]擷取完成：{len(results)} 個檔案[/green]")

    if do_ingest and results:
        kb = _init_kb()
        count = _ingest_fetch_results(results, kb)
        console.print(f"[green]已匯入 {count} 筆至知識庫[/green]")
        console.print(f"目前資料庫統計：{kb.get_stats()}")


@app.command("list-docs")
def list_docs(
    collection: str = typer.Option("all", "--collection", "-c", help="集合名稱（examples/regulations/policies/all）"),
    limit: int = typer.Option(50, "--limit", "-n", help="最大顯示數量"),
) -> None:
    """
    列出知識庫中所有文件的詳細資訊。

    範例：

        gov-ai kb list-docs                         列出所有集合的文件

        gov-ai kb list-docs -c examples              僅列出範例集合

        gov-ai kb list-docs -c regulations -n 20     列出法規集合前 20 筆
    """
    kb = _init_kb()

    if not kb.is_available:
        console.print("[red]錯誤：知識庫不可用。[/red]")
        raise typer.Exit(1)

    collection_map = {
        "examples": ("examples", kb.examples_collection),
        "regulations": ("regulations", kb.regulations_collection),
        "policies": ("policies", kb.policies_collection),
    }

    if collection == "all":
        targets = list(collection_map.values())
    elif collection in collection_map:
        targets = [collection_map[collection]]
    else:
        console.print(f"[red]錯誤：未知集合 '{collection}'，請使用 examples/regulations/policies/all[/red]")
        raise typer.Exit(1)

    table = Table(title="知識庫文件清單", show_lines=True)
    table.add_column("#", style="dim", no_wrap=True, width=4)
    table.add_column("集合", style="cyan", no_wrap=True, width=12)
    table.add_column("ID", style="dim", max_width=20)
    table.add_column("標題", style="green")
    table.add_column("類型", style="magenta", width=8)

    row_num = 0
    for coll_name, coll in targets:
        try:
            data = coll.get(include=["metadatas"])
            ids = data.get("ids", []) if data else []
            metadatas = data.get("metadatas", []) if data else []
            for i, doc_id in enumerate(ids):
                if row_num >= limit:
                    break
                meta = metadatas[i] if i < len(metadatas) else {}
                row_num += 1
                table.add_row(
                    str(row_num),
                    coll_name,
                    doc_id[:16] + "...",
                    meta.get("title", "無標題") if isinstance(meta, dict) else "無標題",
                    meta.get("doc_type", "-") if isinstance(meta, dict) else "-",
                )
        except Exception as e:
            console.print(f"[yellow]讀取集合 '{coll_name}' 時發生錯誤：{e}[/yellow]")

    if row_num == 0:
        console.print("[yellow]知識庫目前為空。[/yellow]")
    else:
        console.print(table)
        console.print(f"共顯示 {row_num} 筆文件")


@app.command("delete")
def delete_doc(
    doc_id: str = typer.Option(..., "--id", help="要刪除的文件 ID"),
    collection: str = typer.Option(
        "examples", "--collection", "-c",
        help="文件所在集合（examples/regulations/policies）",
    ),
) -> None:
    """
    從知識庫刪除單筆文件。

    範例：

        gov-ai kb delete --id "abc-123" -c examples
    """
    kb = _init_kb()

    if not kb.is_available:
        console.print("[red]錯誤：知識庫不可用。[/red]")
        raise typer.Exit(1)

    collection_map = {
        "examples": kb.examples_collection,
        "regulations": kb.regulations_collection,
        "policies": kb.policies_collection,
    }

    coll = collection_map.get(collection)
    if not coll:
        console.print(f"[red]錯誤：未知集合 '{collection}'，請使用 examples/regulations/policies[/red]")
        raise typer.Exit(1)

    # 確認文件存在
    try:
        existing = coll.get(ids=[doc_id])
        if not existing or not existing.get("ids"):
            console.print(f"[red]錯誤：在集合 '{collection}' 中找不到 ID '{doc_id}'[/red]")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]查詢失敗：{e}[/red]")
        raise typer.Exit(1)

    try:
        coll.delete(ids=[doc_id])
        kb.invalidate_cache()
        console.print(f"[green]已從 '{collection}' 刪除文件 {doc_id}[/green]")
    except Exception as e:
        console.print(f"[red]刪除失敗：{e}[/red]")
        raise typer.Exit(1)


@app.command("collections")
def list_collections() -> None:
    """
    列出知識庫中所有集合及其文件數量。

    範例：

        gov-ai kb collections
    """
    kb = _init_kb()

    if not kb.is_available:
        console.print("[red]錯誤：知識庫不可用。[/red]")
        raise typer.Exit(1)

    try:
        colls = kb.client.list_collections()
    except Exception as e:
        console.print(f"[red]無法列出集合：{e}[/red]")
        raise typer.Exit(1)

    table = Table(title="ChromaDB 集合清單", show_lines=True)
    table.add_column("集合名稱", style="cyan")
    table.add_column("文件數量", style="magenta", justify="right")
    table.add_column("metadata", style="dim")

    total = 0
    for c in colls:
        count = c.count()
        total += count
        meta_str = json.dumps(c.metadata, ensure_ascii=False) if c.metadata else "-"
        table.add_row(c.name, str(count), meta_str)

    table.add_row("[bold]合計[/bold]", f"[bold]{total}[/bold]", "")
    console.print(table)


@app.command("details")
def details() -> None:
    """
    顯示知識庫的詳細統計資訊，包含儲存路徑和大小。

    範例：

        gov-ai kb details
    """
    kb = _init_kb()

    if not kb.is_available:
        console.print("[red]錯誤：知識庫不可用。[/red]")
        raise typer.Exit(1)

    stats = kb.get_stats()
    persist_path = Path(kb.persist_path)

    # 計算儲存大小
    total_size = 0
    if persist_path.exists():
        for f in persist_path.rglob("*"):
            if f.is_file():
                total_size += f.stat().st_size

    if total_size >= 1024 * 1024:
        size_str = f"{total_size / (1024 * 1024):.2f} MB"
    elif total_size >= 1024:
        size_str = f"{total_size / 1024:.2f} KB"
    else:
        size_str = f"{total_size} B"

    table = Table(title="知識庫詳細資訊", show_lines=True)
    table.add_column("項目", style="cyan", no_wrap=True)
    table.add_column("值", style="green")

    table.add_row("儲存路徑", str(persist_path.resolve()))
    table.add_row("儲存大小", size_str)
    table.add_row("examples 文件數", str(stats.get("examples_count", 0)))
    table.add_row("regulations 文件數", str(stats.get("regulations_count", 0)))
    table.add_row("policies 文件數", str(stats.get("policies_count", 0)))

    total = sum(stats.values())
    table.add_row("[bold]文件總數[/bold]", f"[bold]{total}[/bold]")

    console.print(table)


@app.command("export-json")
def export_data(
    output_path: str = typer.Option("kb_export.json", "--output", "-o", help="匯出檔案路徑"),
) -> None:
    """
    將知識庫統計和文件清單匯出為 JSON。

    範例：

        gov-ai kb export-json

        gov-ai kb export-json -o my_export.json
    """
    kb = _init_kb()

    if not kb.is_available:
        console.print("[red]錯誤：知識庫不可用。[/red]")
        raise typer.Exit(1)

    stats = kb.get_stats()
    persist_path = Path(kb.persist_path)

    # 收集各集合的文件 ID 清單
    collections_info = {}
    for name, coll in [
        ("examples", kb.examples_collection),
        ("regulations", kb.regulations_collection),
        ("policies", kb.policies_collection),
    ]:
        try:
            data = coll.get(include=["metadatas"])
            ids = data.get("ids", []) if data else []
            metadatas = data.get("metadatas", []) if data else []
            docs_list = []
            for i, doc_id in enumerate(ids):
                meta = metadatas[i] if i < len(metadatas) else {}
                docs_list.append({"id": doc_id, "title": meta.get("title", "無標題")})
            collections_info[name] = {"count": len(ids), "documents": docs_list}
        except Exception as e:
            console.print(f"[dim]讀取集合 {name} 失敗：{e}[/dim]")
            collections_info[name] = {"count": 0, "documents": []}

    export = {
        "persist_path": str(persist_path.resolve()),
        "stats": stats,
        "total_documents": sum(stats.values()),
        "collections": collections_info,
    }

    out = Path(output_path)
    out.write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]已匯出至 {out.resolve()}[/green]")


@app.command(name="export")
def kb_export(
    output: str = typer.Option("kb_export.zip", "-o", "--output", help="匯出 ZIP 路徑"),
) -> None:
    """將知識庫資料匯出為 ZIP 壓縮檔。"""
    import zipfile
    try:
        from src.core.config import ConfigManager
        cm = ConfigManager()
        kb_path = cm.config.get("knowledge_base", {}).get("path", "./kb_data")
    except Exception as e:
        console.print(f"[dim]設定檔載入失敗，使用預設路徑：{e}[/dim]")
        kb_path = "./kb_data"

    if not os.path.isdir(kb_path):
        console.print(f"[yellow]知識庫目錄不存在：{kb_path}[/yellow]")
        raise typer.Exit(1)

    file_count = 0
    total_size = 0

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(kb_path):
            for f in files:
                fp = os.path.join(root, f)
                arcname = os.path.relpath(fp, kb_path)
                zf.write(fp, arcname)
                file_count += 1
                total_size += os.path.getsize(fp)

    if file_count == 0:
        console.print("[yellow]知識庫為空，無資料可匯出。[/yellow]")
        os.remove(output)
        return

    zip_size = os.path.getsize(output)
    console.print(f"[green]已匯出 {file_count} 個檔案至 {output}[/green]")
    console.print(f"[dim]原始大小：{total_size:,} bytes → 壓縮後：{zip_size:,} bytes[/dim]")


@app.command()
def info() -> None:
    """顯示知識庫資訊總覽。"""
    import os
    from datetime import datetime
    try:
        from src.core.config import ConfigManager
        cm = ConfigManager()
        kb_path = cm.config.get("knowledge_base", {}).get("path", "./kb_data")
    except Exception as e:
        console.print(f"[dim]設定檔載入失敗，使用預設路徑：{e}[/dim]")
        kb_path = "./kb_data"

    if not os.path.isdir(kb_path):
        console.print(f"[yellow]知識庫目錄不存在：{kb_path}[/yellow]")
        console.print("[dim]請先執行 gov-ai kb fetch-laws 匯入資料。[/dim]")
        return

    # 統計
    total_files = 0
    total_size = 0
    categories = {}
    latest_mtime = 0

    for root, dirs, files in os.walk(kb_path):
        for f in files:
            fp = os.path.join(root, f)
            total_files += 1
            fsize = os.path.getsize(fp)
            total_size += fsize
            mtime = os.path.getmtime(fp)
            if mtime > latest_mtime:
                latest_mtime = mtime

            # 分類（以子目錄名稱為類別）
            rel = os.path.relpath(root, kb_path)
            cat = rel.split(os.sep)[0] if rel != "." else "根目錄"
            categories[cat] = categories.get(cat, 0) + 1

    from rich.table import Table

    console.print(f"\n[bold cyan]知識庫路徑：[/bold cyan]{os.path.abspath(kb_path)}")
    console.print(f"[bold cyan]文件總數：[/bold cyan]{total_files}")
    console.print(f"[bold cyan]總大小：[/bold cyan]{total_size:,} bytes")

    if latest_mtime > 0:
        last_update = datetime.fromtimestamp(latest_mtime).strftime("%Y-%m-%d %H:%M:%S")
        console.print(f"[bold cyan]最後更新：[/bold cyan]{last_update}")

    if categories:
        table = Table(title="各類別文件數")
        table.add_column("類別", style="cyan")
        table.add_column("文件數", style="green", justify="right")
        for cat, cnt in sorted(categories.items()):
            table.add_row(cat, str(cnt))
        console.print(table)


@app.command(name="stats-detail")
def stats_detail(
    kb_path: str = typer.Option("./kb_data", "--path", "-p", help="知識庫路徑"),
) -> None:
    """
    顯示知識庫目錄的詳細統計資訊（各子目錄的檔案數、大小、最後修改時間）。

    範例：

        gov-ai kb stats-detail

        gov-ai kb stats-detail --path ./my_kb
    """
    from datetime import datetime

    kb_dir = Path(kb_path)
    if not kb_dir.exists():
        console.print(f"[red]找不到知識庫：{kb_path}[/red]")
        raise typer.Exit(1)

    # 掃描子目錄
    subdirs = [d for d in sorted(kb_dir.iterdir()) if d.is_dir()]

    if not subdirs:
        console.print("[yellow]知識庫為空，沒有任何子目錄。[/yellow]")
        return

    table = Table(title="知識庫統計", show_lines=True)
    table.add_column("目錄", style="cyan")
    table.add_column("檔案數", style="magenta", justify="right")
    table.add_column("大小 (KB)", style="green", justify="right")
    table.add_column("最後修改", style="dim")

    for subdir in subdirs:
        files = [f for f in subdir.rglob("*") if f.is_file()]
        file_count = len(files)
        total_size = sum(f.stat().st_size for f in files)
        size_kb = f"{total_size / 1024:.1f}"

        if files:
            latest_mtime = max(f.stat().st_mtime for f in files)
            last_modified = datetime.fromtimestamp(latest_mtime).strftime("%Y-%m-%d %H:%M:%S")
        else:
            last_modified = "-"

        table.add_row(subdir.name, str(file_count), size_kb, last_modified)

    console.print(table)


@app.command(name="list-sources")
def list_sources(
    kb_path: str = typer.Option("./kb_data", "--path", "-p", help="知識庫路徑"),
) -> None:
    """列出知識庫中的所有來源檔案。"""
    if not os.path.isdir(kb_path):
        console.print(f"[red]找不到知識庫目錄：{kb_path}[/red]")
        raise typer.Exit(1)

    files = []
    for root, dirs, filenames in os.walk(kb_path):
        for fname in filenames:
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, kb_path)
            size = os.path.getsize(fpath)
            files.append({"path": rel, "size": size})

    if not files:
        console.print("[yellow]知識庫中尚無來源檔案。[/yellow]")
        return

    table = Table(title="知識庫來源檔案")
    table.add_column("檔案路徑", style="cyan")
    table.add_column("大小", style="green", justify="right")
    for f in sorted(files, key=lambda x: x["path"]):
        size_str = f"{f['size']:,} bytes"
        table.add_row(f["path"], size_str)
    console.print(table)
    console.print(f"\n[dim]共 {len(files)} 個檔案。[/dim]")


if __name__ == "__main__":
    app()
