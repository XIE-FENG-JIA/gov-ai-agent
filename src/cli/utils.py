"""CLI 共用工具函數。

消除跨模組重複的 JSON / YAML 讀寫與檔案處理邏輯。
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import time
from typing import Any

import yaml
from rich.console import Console

logger = logging.getLogger(__name__)

console = Console()
_ATOMIC_TMP_PREFIXES = (".json_", ".txt_", ".yaml_")
_ATOMIC_TMP_MAX_AGE_SECONDS = 3600


def _cleanup_stale_atomic_tmps(parent: str, *, now: float | None = None) -> None:
    """清掉原子寫入遺留超過一小時的暫存檔。"""
    try:
        entries = list(os.scandir(parent))
    except OSError:
        return

    now_ts = time.time() if now is None else now
    for entry in entries:
        if not entry.is_file():
            continue
        name = entry.name
        if not name.endswith(".tmp") or not name.startswith(_ATOMIC_TMP_PREFIXES):
            continue
        try:
            if now_ts - entry.stat().st_mtime <= _ATOMIC_TMP_MAX_AGE_SECONDS:
                continue
            os.unlink(entry.path)
        except OSError:
            continue


def atomic_json_write(path: str, data: Any) -> None:
    """原子寫入 JSON 檔案（先寫暫存檔再 rename，防止中途崩潰損毀）。

    與 config.py / org_memory.py 使用相同的 tempfile + os.replace 策略。
    """
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    _cleanup_stale_atomic_tmps(parent)
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
    _cleanup_stale_atomic_tmps(parent)
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
    _cleanup_stale_atomic_tmps(parent)
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


_CONFIG_SHRINK_THRESHOLD = 0.5  # 新 config top-level key 數量低於舊的 50% 時觸發保護


def safe_config_write(path: str, data: dict[str, Any]) -> None:
    """帶 shrink guard 的 config 寫入——防止意外清空設定檔。

    寫入前檢查：如果新 config 的 top-level key 數量比現有檔案少超過
    50%，先建立 ``.bak`` 備份並記錄警告，再執行寫入。這能防止
    ``config set`` 或 ``fetch-models -u`` 在 config 已損毀時進一步
    丟失資料（備份可用 ``config restore`` 還原）。

    即使新 config 通過檢查，只要舊檔案存在就會建立 ``.bak``。
    """
    bak_path = path + ".bak"

    # 讀取現有 config 做比較
    existing_keys: set[str] = set()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = yaml.safe_load(f)
            if isinstance(existing, dict):
                existing_keys = set(existing.keys())
        except (yaml.YAMLError, UnicodeDecodeError, OSError):
            pass  # 讀取失敗就跳過比較，正常寫入

        # 備份：獨立 try-except，讀取失敗不影響備份嘗試
        if existing_keys:
            try:
                shutil.copy2(path, bak_path)
            except OSError as e:
                logger.warning("無法建立設定檔備份 %s：%s", bak_path, e)

    new_keys = set(data.keys()) if isinstance(data, dict) else set()

    if existing_keys and new_keys:
        ratio = len(new_keys) / len(existing_keys)
        if ratio < _CONFIG_SHRINK_THRESHOLD:
            logger.warning(
                "config shrink guard: 新 config 只有 %d 個 top-level key "
                "（舊有 %d 個，縮減 %.0f%%）。已備份至 %s。"
                "若非預期，請執行 gov-ai config restore 還原。",
                len(new_keys),
                len(existing_keys),
                (1 - ratio) * 100,
                bak_path,
            )

    atomic_yaml_write(path, data)


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
