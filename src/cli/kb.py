import typer
from pathlib import Path
from typing import Any, Dict, Tuple
from rich.console import Console
from rich.table import Table
from src.core.config import ConfigManager
from src.core.llm import get_llm_factory
from src.knowledge.manager import KnowledgeBaseManager

console = Console()
app = typer.Typer()

def parse_markdown_with_metadata(file_path: Path) -> Tuple[Dict[str, Any], str]:
    """解析含有 YAML frontmatter 的 Markdown 檔案。"""
    content = file_path.read_text(encoding='utf-8')
    if content.startswith('---'):
        try:
            parts = content.split('---', 2)
            if len(parts) >= 3:
                import yaml
                metadata = yaml.safe_load(parts[1])
                body = parts[2].strip()
                return metadata, body
        except Exception as e:
            console.print(f"[yellow]解析 {file_path.name} 時發生警告：{e}[/yellow]")
    
    # Fallback
    return {}, content

@app.command()
def ingest(
    source_dir: str = typer.Option("./kb_data/examples", help="要匯入的 Markdown 檔案所在目錄"),
    collection: str = typer.Option("examples", "--collection", "-c", help="目標集合（examples/regulations）"),
    reset: bool = typer.Option(False, help="匯入前重設資料庫")
):
    """
    將 Markdown 檔案匯入知識庫。
    """
    config_manager = ConfigManager()
    config = config_manager.config

    # 初始化 LLM 和 DB（傳入完整設定以避免重複讀取設定檔）
    llm = get_llm_factory(config["llm"], full_config=config)
    kb_path = config["knowledge_base"]["path"]
    kb = KnowledgeBaseManager(persist_path=kb_path, llm_provider=llm)

    if reset:
        console.print("[bold red]正在重設知識庫...[/bold red]")
        kb.reset_db()

    source_path = Path(source_dir)
    if not source_path.exists():
        console.print(f"[red]找不到來源目錄：{source_dir}[/red]")
        raise typer.Exit(1)

    files = list(source_path.glob("*.md"))
    console.print(f"在 {source_dir} 中找到 {len(files)} 個 Markdown 檔案")

    success_count = 0
    skipped_count = 0
    with typer.progressbar(files, label=f"正在匯入至 '{collection}'") as progress:
        for file_path in progress:
            metadata, content = parse_markdown_with_metadata(file_path)

            # 跳過已棄用的文件
            if metadata.get("deprecated"):
                console.print(f"[yellow]跳過已棄用檔案：{file_path.name}[/yellow]")
                skipped_count += 1
                continue

            # Ensure essential metadata
            if "title" not in metadata:
                metadata["title"] = file_path.stem
            if "doc_type" not in metadata:
                metadata["doc_type"] = "unknown"

            # Sanitize metadata for ChromaDB
            import datetime
            import json
            clean_metadata = {}
            for k, v in metadata.items():
                if isinstance(v, (datetime.date, datetime.datetime)):
                    clean_metadata[k] = v.isoformat()
                elif isinstance(v, list):
                    clean_metadata[k] = json.dumps(v, ensure_ascii=False) 
                elif isinstance(v, (str, int, float, bool, type(None))):
                    clean_metadata[k] = v
                else:
                    clean_metadata[k] = str(v)

            kb.add_document(content, clean_metadata, collection_name=collection)
            success_count += 1

    if skipped_count > 0:
        console.print(f"[yellow]已跳過 {skipped_count} 筆已棄用文件。[/yellow]")
    console.print(f"[green]成功匯入 {success_count} 筆文件至 '{collection}'！[/green]")
    stats = kb.get_stats()
    console.print(f"目前資料庫統計：{stats}")

@app.command()
def search(
    query: str = typer.Argument(..., help="搜尋關鍵字"),
    limit: int = typer.Option(3, help="回傳結果數量")
):
    """
    在知識庫中搜尋相關文件。
    """
    config_manager = ConfigManager()
    config = config_manager.config

    # 初始化 LLM 和 DB（傳入完整設定以避免重複讀取設定檔）
    llm = get_llm_factory(config["llm"], full_config=config)
    kb_path = config["knowledge_base"]["path"]
    kb = KnowledgeBaseManager(persist_path=kb_path, llm_provider=llm)

    console.print(f"正在搜尋：[bold cyan]{query}[/bold cyan]...")
    results = kb.search_examples(query, n_results=limit)

    if not results:
        console.print("[yellow]找不到符合的文件。[/yellow]")
        return

    table = Table(title=f"搜尋結果（前 {len(results)} 筆）")
    table.add_column("相似度", style="magenta", no_wrap=True)
    table.add_column("類型", style="cyan")
    table.add_column("標題", style="green")
    table.add_column("摘要")

    for res in results:
        distance = res.get("distance", 0)
        score = f"{1 - distance:.2f}" if distance is not None else "N/A"  # 餘弦距離 -> 相似度
        metadata = res.get("metadata", {})
        content = res.get("content", "")
        excerpt = content[:100].replace('\n', ' ') + "..." if content else "（無內容）"

        table.add_row(
            score,
            metadata.get("doc_type", "未知") if isinstance(metadata, dict) else "未知",
            metadata.get("title", "無標題") if isinstance(metadata, dict) else "無標題",
            excerpt
        )
    
    console.print(table)

if __name__ == "__main__":
    app()
