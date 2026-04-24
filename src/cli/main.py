import logging
import sys

import typer
from rich.console import Console

from src import __version__

_DIRECT_COMMANDS = (
    ("generate", "根據自然語言輸入產生完整的政府公文。"),
    ("switch", "互動式切換目前使用的 LLM 提供者。"),
    ("types", "列出所有支援的公文類型及其說明。"),
    ("quickstart", "快速開始引導：檢查環境、設定並產生範例公文。"),
    ("validate", "驗證現有公文 .docx 檔案是否符合格式規範。"),
    ("stats", "顯示系統使用統計和知識庫概覽。"),
    ("doctor", "快速診斷系統環境和常見問題。"),
    ("sample", "顯示公文格式範例供參考。"),
    ("compare", "比較兩個草稿版本的差異。"),
    ("explain", "解析公文結構，列出各段落內容與缺少的段落。"),
    ("template", "顯示公文骨架範本，包含佔位符供快速填寫。"),
    ("diff", "比較兩份公文檔案的差異。"),
    ("convert", "將 .docx 公文轉換為 Markdown 或純文字格式。"),
    ("checklist", "檢核公文是否包含所有必要欄位，確認可發文。"),
    ("search", "搜尋生成歷史中包含關鍵字的公文記錄。"),
    ("status", "顯示系統狀態總覽儀表板。"),
    ("rewrite", "讀取現有公文並改寫為指定風格。"),
    ("lint", "輕量公文用語與格式檢查。"),
    ("merge", "合併多份公文片段為一份完整公文。"),
    ("archive", "將公文檔案封存為 ZIP 壓縮檔。"),
    ("preview", "預覽公文的格式化結構。"),
    ("count", "統計公文的字數、行數與段落資訊。"),
    ("split", "將公文依段落拆分為獨立檔案。"),
    ("toc", "生成公文目錄摘要。"),
    ("redact", "遮蔽公文中的個人資料。"),
    ("stamp", "為公文檔案加蓋電子戳記。"),
    ("verify", "驗證知識庫或輸出文件的引用與來源一致性。"),
    ("number", "產生公文編號。"),
    ("extract", "擷取公文欄位內容。"),
    ("format", "格式化公文文件，統一關鍵字格式與段落縮排。"),
    ("summarize", "摘要公文內容，擷取主旨與說明。"),
    ("replace", "批量替換公文中的指定文字。"),
    ("highlight", "標記公文中的關鍵詞並顯示統計。"),
    ("review", "對現有草稿執行多 Agent 審查，輸出具體修改建議。"),
    ("cite", "法規引用建議 - 給定公文草稿，推薦適用法規與標準引用格式。"),
    ("wizard", "互動式公文精靈 — 逐步引導，無需記憶 CLI 參數。"),
)

_GROUP_COMMANDS = (
    ("kb", "知識庫管理指令"),
    ("config", "組態設定工具"),
    ("history", "生成歷史記錄"),
    ("workflow", "工作流程範本管理"),
    ("batch", "批次處理工具"),
    ("org-memory", "組織記憶管理"),
    ("feedback", "公文品質回饋"),
    ("open-notebook", "open-notebook seam smoke tools"),
    ("sources", "公開政府資料來源"),
    ("glossary", "公文語彙查詢"),
    ("alias", "指令別名管理"),
    ("profile", "使用者設定檔"),
)


def _is_help_only_invocation(argv: list[str] | None = None) -> bool:
    """只顯示頂層 help/version/completion 時，避免重型指令模組冷啟動。"""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        return False
    help_only_flags = {"--help", "-h", "--version", "-v", "--show-completion", "--install-completion"}
    return all(arg in help_only_flags for arg in args)


def _register_help_stubs(app: typer.Typer) -> None:
    """為 help-only 模式註冊輕量 stub，保留指令目錄。"""

    def _stub_command(name: str) -> None:
        raise RuntimeError(f"help-only stub should not execute: {name}")

    for name, help_text in _DIRECT_COMMANDS:
        stub = lambda _name=name: _stub_command(_name)
        stub.__name__ = f"{name.replace('-', '_')}_stub"
        stub.__doc__ = help_text
        app.command(name=name, help=help_text)(stub)

    for name, help_text in _GROUP_COMMANDS:
        sub_app = typer.Typer(help=help_text)
        app.add_typer(sub_app, name=name, help=help_text)

app = typer.Typer(
    name="gov-ai",
    help="台灣政府公文 AI 智慧助理",
    no_args_is_help=True,
)
if _is_help_only_invocation():
    _register_help_stubs(app)
else:
    from src.cli import batch_tools
    from src.cli import config_tools
    from src.cli import feedback_cmd
    from src.cli import generate
    from src.cli import glossary_cmd
    from src.cli import history
    from src.cli import kb
    from src.cli import open_notebook_cmd
    from src.cli import org_memory_cmd
    from src.cli import profile_cmd
    from src.cli import sources_cmd
    from src.cli import switcher
    from src.cli import workflow_cmd
    from src.cli.alias_cmd import app as alias_app
    from src.cli.archive_cmd import archive as archive_cmd
    from src.cli.checklist_cmd import checklist as checklist_cmd
    from src.cli.cite_cmd import cite as cite_cmd
    from src.cli.compare_cmd import compare as compare_cmd
    from src.cli.convert_cmd import convert as convert_cmd
    from src.cli.count_cmd import count as count_cmd
    from src.cli.diff_cmd import diff as diff_cmd
    from src.cli.doctor import doctor as doctor_cmd
    from src.cli.explain_cmd import explain as explain_cmd
    from src.cli.extract_cmd import extract as extract_cmd
    from src.cli.format_cmd import format_doc as format_cmd
    from src.cli.highlight_cmd import highlight as highlight_cmd
    from src.cli.lint_cmd import lint as lint_cmd
    from src.cli.merge_cmd import merge as merge_cmd
    from src.cli.number_cmd import number as number_cmd
    from src.cli.preview_cmd import preview as preview_cmd
    from src.cli.quickstart import quickstart as quickstart_cmd
    from src.cli.redact_cmd import redact as redact_cmd
    from src.cli.replace_cmd import replace_text as replace_cmd
    from src.cli.review_cmd import review as review_cmd
    from src.cli.rewrite_cmd import rewrite as rewrite_cmd
    from src.cli.sample_cmd import sample as sample_cmd
    from src.cli.search_cmd import search as search_cmd
    from src.cli.split_cmd import split as split_cmd
    from src.cli.stamp_cmd import stamp as stamp_cmd
    from src.cli.stats_cmd import stats as stats_cmd
    from src.cli.status_cmd import status as status_dashboard_cmd
    from src.cli.summarize_cmd import summarize as summarize_cmd
    from src.cli.template_cmd import template as template_cmd
    from src.cli.toc_cmd import toc as toc_cmd
    from src.cli.types_cmd import types_command
    from src.cli.validate_cmd import validate as validate_cmd
    from src.cli.verify_cmd import verify as verify_cmd
    from src.cli.wizard_cmd import wizard as wizard_cmd

    app.add_typer(kb.app, name="kb", help="知識庫管理指令")
    app.add_typer(config_tools.app, name="config", help="組態設定工具")
    app.add_typer(history.app, name="history", help="生成歷史記錄")
    app.add_typer(workflow_cmd.app, name="workflow", help="工作流程範本管理")
    app.add_typer(batch_tools.app, name="batch", help="批次處理工具")
    app.add_typer(org_memory_cmd.app, name="org-memory", help="組織記憶管理")
    app.add_typer(feedback_cmd.app, name="feedback", help="公文品質回饋")
    app.add_typer(open_notebook_cmd.app, name="open-notebook", help="open-notebook 整合 smoke")
    app.add_typer(sources_cmd.app, name="sources", help="公開政府資料來源")
    app.add_typer(open_notebook_cmd.app, name="open-notebook", help="open-notebook seam smoke tools")
    app.add_typer(glossary_cmd.app, name="glossary", help="公文語彙查詢")
    app.add_typer(alias_app, name="alias", help="指令別名管理")
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
    app.command(name="verify")(verify_cmd)
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
    from src.core.logging_config import setup_logging

    configure_state_dir()
    level = logging.DEBUG if verbose else None  # None → 讀取 LOG_LEVEL 環境變數（預設 INFO）
    setup_logging(level=level)

if __name__ == "__main__":
    app()
