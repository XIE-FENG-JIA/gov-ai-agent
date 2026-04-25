import concurrent.futures
import csv
import json
import os
import re
import sys
import threading
import time

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeElapsedColumn
from rich.status import Status

from src.agents.editor import EditorInChief
from src.agents.requirement import RequirementAgent
from src.agents.template import TemplateEngine
from src.agents.writer import WriterAgent
from src.cli.history import append_record
from src.cli.utils_io import atomic_json_write, atomic_text_write
from src.core.config import ConfigManager
from src.core.constants import MAX_USER_INPUT_LENGTH
from src.core.error_analyzer import ErrorAnalyzer
from src.core.llm import LiteLLMProvider, get_llm_factory
from src.document.exporter import DocxExporter
from src.knowledge.manager import KnowledgeBaseManager
from src.utils.lang_check import check_language
from src.utils.tw_check import detect_simplified

console = Console()
app = typer.Typer()

_INPUT_MIN_LENGTH = 5
_INPUT_MAX_LENGTH = MAX_USER_INPUT_LENGTH
_PATH_PATTERN = re.compile(r"[A-Za-z]:\\[\w\\. -]+|/[\w/. -]{5,}")

_FORMAT_OPTION_DEFS: tuple[tuple[str, str, dict[str, str], str | None, str | None], ...] = (
    ("speed", "生成模式", {"fast": "快速模式", "normal": "標準模式", "careful": "謹慎模式"}, None, None),
    ("margin", "頁邊距", {"standard": "標準邊距", "narrow": "窄邊距", "wide": "寬邊距"}, None, None),
    ("line_spacing", "行距", {"1.0": "單行距", "1.5": "1.5 倍行距", "2.0": "雙倍行距"}, None, None),
    ("font_size", "字型大小", {"10": "10pt", "12": "12pt", "14": "14pt", "16": "16pt"}, None, None),
    ("duplex", "列印模式", {"off": "單面列印", "long-edge": "雙面列印（長邊翻轉）", "short-edge": "雙面列印（短邊翻轉）"}, None, None),
    ("orientation", "紙張方向", {"portrait": "直印", "landscape": "橫印"}, None, None),
    ("paper_size", "紙張大小", {"a4": "A4 (210×297mm)", "b4": "B4 (257×364mm)", "a3": "A3 (297×420mm)", "letter": "Letter (216×279mm)"}, None, "A4/B4/A3/Letter"),
    ("columns", "排版", {"1": "單欄排版", "2": "雙欄排版"}, None, None),
    ("seal", "用印", {"none": "免用印", "official": "蓋機關印信", "personal": "蓋職章"}, None, None),
    ("draft_mark", "草稿標記", {"none": "無標記", "draft": "草稿", "internal": "內部文件"}, "none", None),
    ("urgency_label", "急件標示", {"normal": "普通件", "urgent": "急件", "most-urgent": "最速件"}, "normal", None),
    ("lang", "公文語言", {"zh-tw": "繁體中文", "zh-cn": "簡體中文", "en": "英文"}, "zh-tw", "zh-TW/zh-CN/en"),
)

from .cli import generate
from .content_metadata import _apply_content_metadata, _display_format_options
from .export import (
    _display_summary,
    _export_document,
    _export_qa_report,
    _save_version,
    _show_cite_suggestions,
    _show_lint_results,
)
from .pipeline import (
    _handle_confirm,
    _handle_dry_run,
    _handle_estimate,
    _init_pipeline,
    _load_batch_csv,
    _process_batch_item,
    _read_interactive_input,
    _resolve_generation_engine,
    _resolve_input,
    _retry_with_backoff,
    _run_batch,
    _run_core_pipeline,
    _sanitize_error,
)

app.command()(generate)

__all__ = [
    "ConfigManager",
    "Console",
    "DocxExporter",
    "EditorInChief",
    "ErrorAnalyzer",
    "KnowledgeBaseManager",
    "LiteLLMProvider",
    "Markdown",
    "Panel",
    "Progress",
    "RequirementAgent",
    "SpinnerColumn",
    "Status",
    "TaskProgressColumn",
    "TemplateEngine",
    "TextColumn",
    "TimeElapsedColumn",
    "WriterAgent",
    "_FORMAT_OPTION_DEFS",
    "_INPUT_MAX_LENGTH",
    "_INPUT_MIN_LENGTH",
    "_PATH_PATTERN",
    "_apply_content_metadata",
    "_display_format_options",
    "_display_summary",
    "_export_document",
    "_export_qa_report",
    "_handle_confirm",
    "_handle_dry_run",
    "_handle_estimate",
    "_init_pipeline",
    "_load_batch_csv",
    "_process_batch_item",
    "_read_interactive_input",
    "_resolve_generation_engine",
    "_resolve_input",
    "_retry_with_backoff",
    "_run_batch",
    "_run_core_pipeline",
    "_sanitize_error",
    "_save_version",
    "_show_cite_suggestions",
    "_show_lint_results",
    "app",
    "append_record",
    "atomic_json_write",
    "atomic_text_write",
    "check_language",
    "concurrent",
    "console",
    "csv",
    "detect_simplified",
    "generate",
    "get_llm_factory",
    "json",
    "os",
    "re",
    "sys",
    "threading",
    "time",
    "typer",
]

if __name__ == "__main__":
    app()
