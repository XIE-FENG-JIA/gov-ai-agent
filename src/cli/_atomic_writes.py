"""原子寫入輔助函數 + orphan 清理 — 先寫暫存檔再 os.replace，防止中途崩潰損毀。

Extracted from src/cli/utils_io.py (T-FAT-WATCH-CUT-V6).  utils_io re-exports
these symbols for backward compatibility so no external imports need changing.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from typing import Any

import yaml

# Prefixes used by atomic write helpers; also used by cleanup_orphan_tmps.
_ATOMIC_TMP_PREFIXES = (".json_", ".txt_", ".yaml_")
_ATOMIC_TMP_MAX_AGE_SECONDS = 3600


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
