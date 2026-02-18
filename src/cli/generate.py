import typer
from rich.console import Console

# Import all our components
from src.core.config import ConfigManager
from src.core.llm import get_llm_factory
from src.knowledge.manager import KnowledgeBaseManager
from src.agents.editor import EditorInChief
from src.agents.requirement import RequirementAgent
from src.agents.writer import WriterAgent
from src.agents.template import TemplateEngine
from src.document.exporter import DocxExporter

console = Console()
app = typer.Typer()

@app.command()
def generate(
    input_text: str = typer.Option(..., "--input", "-i", help="公文需求描述（自然語言）"),
    output_path: str = typer.Option("output.docx", "--output", "-o", help="輸出 .docx 檔案的儲存路徑"),
    skip_review: bool = typer.Option(False, help="跳過多 Agent 審查步驟"),
):
    """
    根據自然語言輸入產生完整的政府公文。
    """
    
    # 0. 初始化（傳入完整設定以避免重複讀取設定檔）
    config_manager = ConfigManager()
    config = config_manager.config
    llm = get_llm_factory(config['llm'], full_config=config)
    kb = KnowledgeBaseManager(config['knowledge_base']['path'], llm)
    
    # 1. 需求分析
    console.rule("[bold blue]1. 需求分析[/bold blue]")
    req_agent = RequirementAgent(llm)
    try:
        requirement = req_agent.analyze(input_text)
        console.print(f"[green]偵測類型：[/green] {requirement.doc_type}")
        console.print(f"[green]主旨：[/green] {requirement.subject}")
    except Exception as e:
        console.print(f"[red]需求分析失敗：{e}[/red]")
        raise typer.Exit(1)

    # 2. 草稿撰寫 (RAG)
    console.rule("[bold blue]2. 草稿撰寫 (RAG)[/bold blue]")
    writer = WriterAgent(llm, kb)
    raw_draft = writer.write_draft(requirement)

    # 3. 格式標準化
    console.rule("[bold blue]3. 格式標準化[/bold blue]")
    template_engine = TemplateEngine()
    sections = template_engine.parse_draft(raw_draft)
    formatted_draft = template_engine.apply_template(requirement, sections)
    
    # 4. 多 Agent 審查與修正
    final_draft = formatted_draft
    qa_report_str = None

    if not skip_review:
        editor = EditorInChief(llm, kb)
        # review_and_refine returns (refined_draft, qa_report_object)
        final_draft, qa_report = editor.review_and_refine(formatted_draft, requirement.doc_type)
        qa_report_str = qa_report.audit_log

    # 5. 匯出
    console.rule("[bold blue]5. 匯出文件[/bold blue]")
    exporter = DocxExporter()
    try:
        final_path = exporter.export(final_draft, output_path, qa_report=qa_report_str)
        console.print(f"[bold green]完成！文件已儲存至：[/bold green] {final_path}")
    except Exception as e:
        console.print(f"[red]匯出失敗：{e}[/red]")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()
