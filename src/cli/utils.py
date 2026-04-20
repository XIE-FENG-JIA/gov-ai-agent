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


def cleanup_orphan_tmps(
    parent: str = ".",
    *,
    max_age_seconds: float | None = _ATOMIC_TMP_MAX_AGE_SECONDS,
    now: float | None = None,
) -> int:
    """清掉原子寫入遺留暫存檔並回傳刪除數量。

    ``max_age_seconds=None`` 時會刪除目錄下所有符合前綴的 orphan tmp。
    預設僅清掉超過一小時的暫存檔，避免誤刪正在寫入中的檔案。
    """
    try:
        entries = list(os.scandir(parent))
    except OSError:
        return 0

    now_ts = time.time() if now is None else now
    removed = 0
    for entry in entries:
        if not entry.is_file():
            continue
        name = entry.name
        if not name.endswith(".tmp") or not name.startswith(_ATOMIC_TMP_PREFIXES):
            continue
        try:
            if max_age_seconds is not None and now_ts - entry.stat().st_mtime <= max_age_seconds:
                continue
            os.unlink(entry.path)
            removed += 1
        except OSError:
            continue
    return removed


def _cleanup_stale_atomic_tmps(parent: str, *, now: float | None = None) -> None:
    """清掉原子寫入遺留超過一小時的暫存檔。"""
    cleanup_orphan_tmps(parent, now=now)


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
