import logging
import typer
from rich.console import Console
from src import __version__
from src.cli import kb
from src.cli import generate
from src.cli import config_tools
from src.cli import switcher
from src.cli.types_cmd import types_command
from src.cli.quickstart import quickstart as quickstart_cmd
from src.cli import history
from src.cli import workflow_cmd
from src.cli import batch_tools
from src.cli import org_memory_cmd
from src.cli import feedback_cmd
from src.cli import sources_cmd
from src.cli import open_notebook_cmd
from src.cli.validate_cmd import validate as validate_cmd
from src.cli.stats_cmd import stats as stats_cmd
from src.cli.doctor import doctor as doctor_cmd
from src.cli.sample_cmd import sample as sample_cmd
from src.cli.compare_cmd import compare as compare_cmd
from src.cli.explain_cmd import explain as explain_cmd
from src.cli.template_cmd import template as template_cmd
from src.cli.diff_cmd import diff as diff_cmd
from src.cli.convert_cmd import convert as convert_cmd
from src.cli import glossary_cmd
from src.cli import alias_cmd
from src.cli import profile_cmd
from src.cli.checklist_cmd import checklist as checklist_cmd
from src.cli.search_cmd import search as search_cmd
from src.cli.status_cmd import status as status_dashboard_cmd
from src.cli.rewrite_cmd import rewrite as rewrite_cmd
from src.cli.lint_cmd import lint as lint_cmd
from src.cli.merge_cmd import merge as merge_cmd
from src.cli.archive_cmd import archive as archive_cmd
from src.cli.preview_cmd import preview as preview_cmd
from src.cli.count_cmd import count as count_cmd
from src.cli.split_cmd import split as split_cmd
from src.cli.toc_cmd import toc as toc_cmd
from src.cli.redact_cmd import redact as redact_cmd
from src.cli.stamp_cmd import stamp as stamp_cmd
from src.cli.number_cmd import number as number_cmd
from src.cli.extract_cmd import extract as extract_cmd
from src.cli.format_cmd import format_doc as format_cmd
from src.cli.summarize_cmd import summarize as summarize_cmd
from src.cli.replace_cmd import replace_text as replace_cmd
from src.cli.highlight_cmd import highlight as highlight_cmd
from src.cli.review_cmd import review as review_cmd
from src.cli.cite_cmd import cite as cite_cmd
from src.cli.wizard_cmd import wizard as wizard_cmd
from src.core.logging_config import setup_logging

app = typer.Typer(
    name="gov-ai",
    help="台灣政府公文 AI 智慧助理",
    no_args_is_help=True,
)
app.add_typer(kb.app, name="kb", help="知識庫管理指令")
app.add_typer(config_tools.app, name="config", help="組態設定工具")
app.add_typer(history.app, name="history", help="生成歷史記錄")
app.add_typer(workflow_cmd.app, name="workflow", help="工作流程範本管理")
app.add_typer(batch_tools.app, name="batch", help="批次處理工具")
app.add_typer(org_memory_cmd.app, name="org-memory", help="組織記憶管理")
app.add_typer(feedback_cmd.app, name="feedback", help="公文品質回饋")
app.add_typer(sources_cmd.app, name="sources", help="公開政府資料來源")
app.add_typer(open_notebook_cmd.app, name="open-notebook", help="open-notebook seam smoke tools")
app.add_typer(glossary_cmd.app, name="glossary", help="公文語彙查詢")
app.add_typer(alias_cmd.app, name="alias", help="指令別名管理")
app.add_typer(profile_cmd.app, name="profile", help="使用者設定檔")
app.command(name="generate")(generate.generate)
app.command(name="switch")(switcher.switch)
app.command(name="types")(types_command)
app.command(name="quickstart")(quickstart_cmd)
app.command(name="validate")(validate_cmd)
app.command(name="stats")(stats_cmd)
app.command(name="doctor")(doctor_cmd)
app.command(name="sample")(sample_cmd)
app.command(name="compare")(compare_cmd)
app.command(name="explain")(explain_cmd)
app.command(name="template")(template_cmd)
app.command(name="diff")(diff_cmd)
app.command(name="convert")(convert_cmd)
app.command(name="checklist")(checklist_cmd)
app.command(name="search")(search_cmd)
app.command(name="status")(status_dashboard_cmd)
app.command(name="rewrite")(rewrite_cmd)
app.command(name="lint")(lint_cmd)
app.command(name="merge")(merge_cmd)
app.command(name="archive")(archive_cmd)
app.command(name="preview")(preview_cmd)
app.command(name="count")(count_cmd)
app.command(name="split")(split_cmd)
app.command(name="toc")(toc_cmd)
app.command(name="redact")(redact_cmd)
app.command(name="stamp")(stamp_cmd)
app.command(name="number")(number_cmd)
app.command(name="extract")(extract_cmd)
app.command(name="format")(format_cmd)
app.command(name="summarize")(summarize_cmd)
app.command(name="replace")(replace_cmd)
app.command(name="highlight")(highlight_cmd)
app.command(name="review")(review_cmd)
app.command(name="cite")(cite_cmd)
app.command(name="wizard")(wizard_cmd)

console = Console()

def version_callback(value: bool) -> None:
    """顯示版本號後結束程式。"""
    if value:
        console.print(f"公文 AI 助理 CLI 版本：[bold green]{__version__}[/bold green]")
        raise typer.Exit()

@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        help="顯示版本資訊並結束。",
        callback=version_callback,
        is_eager=True,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="啟用詳細日誌輸出（DEBUG 等級）。",
    ),
) -> None:
    """
    台灣政府公文 AI 智慧助理。

    使用此 CLI 工具依據公文規範產生、審查與匯出政府公文。

    快速開始：

        gov-ai quickstart          環境檢查與設置引導

        gov-ai generate -i "台北市環保局發給各學校，加強資源回收"

    常用流程：

        gov-ai config init         互動式建立設定檔

        gov-ai kb fetch-laws       匯入法規資料

        gov-ai generate -i "..."   產生公文

        gov-ai validate output.docx  驗證公文格式

        gov-ai history list        查看生成記錄

        gov-ai stats               系統統計總覽

        gov-ai doctor              快速診斷問題
    """
    # Delay state-dir setup import until callback execution so CLI module
    # collection does not depend on src.cli.utils import order.
    from src.cli.utils import configure_state_dir

    configure_state_dir()
    level = logging.DEBUG if verbose else None  # None → 讀取 LOG_LEVEL 環境變數（預設 INFO）
    setup_logging(level=level)

if __name__ == "__main__":
    app()
