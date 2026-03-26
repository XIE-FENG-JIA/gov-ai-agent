"""CLI 共用工具函數。

消除跨模組重複的 JSON / YAML 讀寫與檔案處理邏輯。
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Any

import yaml
from rich.console import Console

console = Console()


def atomic_json_write(path: str, data: Any) -> None:
    """原子寫入 JSON 檔案（先寫暫存檔再 rename，防止中途崩潰損毀）。

    與 config.py / org_memory.py 使用相同的 tempfile + os.replace 策略。
    """
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=parent, suffix=".tmp", prefix=".json_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def atomic_text_write(path: str, content: str, encoding: str = "utf-8") -> None:
    """原子寫入純文字檔案（先寫暫存檔再 rename，防止中途崩潰損毀）。

    與 atomic_json_write 使用相同的 tempfile + os.replace 策略。
    """
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=parent, suffix=".tmp", prefix=".txt_")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def atomic_yaml_write(path: str, data: Any) -> None:
    """原子寫入 YAML 檔案（先寫暫存檔再 rename，防止中途崩潰損毀）。

    與 atomic_json_write 使用相同的 tempfile + os.replace 策略。
    """
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=parent, suffix=".tmp", prefix=".yaml_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


class JSONStore:
    """簡易 JSON 持久化儲存。

    取代散落在多個 CLI 模組中的 _load_X / _save_X 函數對。

    用法::

        store = JSONStore(".gov-ai-history.json", default=[])
        data = store.load()           # list
        data.append(new_record)
        store.save(data)
    """

    def __init__(self, filename: str, *, default: Any = None) -> None:
        self._filename = filename
        self._default = default if default is not None else {}

    @property
    def path(self) -> str:
        return os.path.join(os.getcwd(), self._filename)

    def exists(self) -> bool:
        return os.path.isfile(self.path)

    def load(self) -> Any:
        """讀取 JSON 檔案，失敗時回傳預設值的拷貝。"""
        if not self.exists():
            return _copy_default(self._default)
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return _copy_default(self._default)

    def save(self, data: Any) -> None:
        """原子寫入 JSON 檔案（防止中途崩潰損毀）。"""
        atomic_json_write(self.path, data)


def _copy_default(default: Any) -> Any:
    """回傳預設值的淺拷貝（避免可變物件共用）。"""
    if isinstance(default, list):
        return list(default)
    if isinstance(default, dict):
        return dict(default)
    return default


def read_file_safe(filepath: str, *, encoding: str = "utf-8-sig") -> str | None:
    """安全讀取文字檔案，失敗時回傳 None。

    統一處理 FileNotFoundError 和 UnicodeDecodeError。
    """
    if not os.path.isfile(filepath):
        return None
    try:
        with open(filepath, "r", encoding=encoding) as f:
            return f.read()
    except (UnicodeDecodeError, OSError):
        return None
