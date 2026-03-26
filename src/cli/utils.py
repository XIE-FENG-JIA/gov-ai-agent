"""CLI 共用工具函數。

消除跨模組重複的 JSON 讀寫與檔案處理邏輯。
"""
from __future__ import annotations

import json
import os
from typing import Any

from rich.console import Console

console = Console()


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
        """將資料寫入 JSON 檔案。"""
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


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
