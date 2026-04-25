"""工作流程範本管理指令。"""

import os
import re

import typer
from rich.console import Console

from src.cli.utils_io import resolve_state_path, resolve_state_read_path

app = typer.Typer()
console = Console()

_WORKFLOW_DIR = ".gov-ai-workflows"
_VALID_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def _resolve_workflow_dir(*, for_write: bool) -> str:
    if not for_write:
        return resolve_state_read_path(_WORKFLOW_DIR)
    read_path = resolve_state_read_path(_WORKFLOW_DIR)
    write_path = resolve_state_path(_WORKFLOW_DIR)
    if read_path != write_path and os.path.isdir(read_path) and not os.path.exists(write_path):
        return read_path
    return write_path


def _ensure_dir() -> str:
    """確保工作流程目錄存在並回傳路徑。"""
    workflow_dir = _resolve_workflow_dir(for_write=True)
    os.makedirs(workflow_dir, exist_ok=True)
    return workflow_dir


def _validate_workflow_name(name: str) -> None:
    """驗證工作流程名稱，防止路徑穿越攻擊。"""
    if not _VALID_NAME_RE.match(name):
        raise typer.BadParameter(
            f"範本名稱 '{name}' 包含不允許的字元，"
            "僅允許英數字、底線與連字號 [a-zA-Z0-9_-]。"
        )


def _workflow_path(name: str, *, for_write: bool = False) -> str:
    """取得範本檔案路徑。"""
    _validate_workflow_name(name)
    return os.path.join(_resolve_workflow_dir(for_write=for_write), f"{name}.json")


from . import commands as _commands  # noqa: E402,F401

__all__ = [
    "app",
    "console",
    "_WORKFLOW_DIR",
    "_ensure_dir",
    "_resolve_workflow_dir",
    "_validate_workflow_name",
    "_workflow_path",
]
