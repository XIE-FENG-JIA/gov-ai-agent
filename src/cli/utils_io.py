"""CLI I/O 工具函數：state 路徑管理、原子寫入、JSONStore、安全讀取。

fat-rotate-v3 Track A: utils.py 拆解後的 I/O 核心模組。
Atomic-write helpers extracted to _atomic_writes.py (T-FAT-WATCH-CUT-V6);
re-exported here for backward compatibility.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
from typing import Any

from src.cli._atomic_writes import (  # noqa: F401 — re-exported for callers
    _ATOMIC_TMP_MAX_AGE_SECONDS,
    _ATOMIC_TMP_PREFIXES,
    _cleanup_stale_atomic_tmps,
    atomic_json_write,
    atomic_text_write,
    atomic_yaml_write,
    cleanup_orphan_tmps,
)

logger = logging.getLogger(__name__)

_STATE_DIR_ENV = "GOV_AI_STATE_DIR"
_STATE_DIR_OVERRIDE: str | None = None


def _normalize_state_path(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


def default_state_dir() -> str:
    """回傳 CLI 預設的使用者層級 state dir。"""
    return _normalize_state_path(os.path.join("~", ".gov-ai", "state"))


def set_state_dir(path: str | None) -> None:
    """設定執行期 state dir；傳入 ``None`` 時回到 cwd 模式。"""
    global _STATE_DIR_OVERRIDE
    _STATE_DIR_OVERRIDE = _normalize_state_path(path) if path else None


def get_state_dir() -> str | None:
    """取得目前啟用的 state dir。"""
    return _STATE_DIR_OVERRIDE


def _looks_like_repo_root(cwd: str) -> bool:
    return os.path.isdir(os.path.join(cwd, ".git")) and os.path.isfile(os.path.join(cwd, "program.md"))


def detect_state_dir(cwd: str | None = None) -> str | None:
    """偵測是否應啟用專用 state dir。"""
    raw = os.environ.get(_STATE_DIR_ENV, "").strip()
    if raw:
        return _normalize_state_path(raw)
    current = os.path.abspath(cwd or os.getcwd())
    if _looks_like_repo_root(current):
        return default_state_dir()
    return None


def configure_state_dir(cwd: str | None = None) -> str | None:
    """依環境與工作目錄設定 state dir，並回傳結果。"""
    state_dir = detect_state_dir(cwd)
    set_state_dir(state_dir)
    return state_dir


def resolve_state_path(relative_path: str, *, cwd: str | None = None, state_dir: str | None = None) -> str:
    """回傳 state 檔案的寫入路徑。"""
    if os.path.isabs(relative_path):
        return relative_path
    base_dir = state_dir if state_dir is not None else get_state_dir()
    if base_dir:
        return os.path.join(base_dir, relative_path)
    current = os.path.abspath(cwd or os.getcwd())
    return os.path.join(current, relative_path)


def resolve_state_read_path(relative_path: str, *, cwd: str | None = None, state_dir: str | None = None) -> str:
    """回傳 state 檔案的讀取路徑；若新路徑尚不存在，回退到 cwd 舊位置。"""
    primary = resolve_state_path(relative_path, cwd=cwd, state_dir=state_dir)
    if os.path.isfile(primary) or os.path.isdir(primary):
        return primary
    if os.path.isabs(relative_path):
        return primary
    current = os.path.abspath(cwd or os.getcwd())
    legacy = os.path.join(current, relative_path)
    if os.path.isfile(legacy) or os.path.isdir(legacy):
        return legacy
    return primary



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

    existing_keys: set[str] = set()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = yaml.safe_load(f)
            if isinstance(existing, dict):
                existing_keys = set(existing.keys())
        except (yaml.YAMLError, UnicodeDecodeError, OSError):
            pass

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
        return resolve_state_path(self._filename)

    @property
    def read_path(self) -> str:
        return resolve_state_read_path(self._filename)

    def exists(self) -> bool:
        return os.path.isfile(self.read_path)

    def load(self) -> Any:
        """讀取 JSON 檔案，失敗時回傳預設值的拷貝。"""
        if not self.exists():
            return _copy_default(self._default)
        try:
            with open(self.read_path, "r", encoding="utf-8") as f:
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
