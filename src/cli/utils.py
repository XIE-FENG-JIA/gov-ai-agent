"""CLI 共用工具函數（shim）— fat-rotate-v3 後向相容橋接層。

所有實作已移至：
- :mod:`src.cli.utils_io`      — I/O 核心（state 路徑、原子寫入、JSONStore、safe read）
- :mod:`src.cli.utils_display` — Rich console singleton
- :mod:`src.cli.utils_text`    — 文字正規化（目前為空）

此模組保留為向後相容 shim，供尚未更新的呼叫方使用。
新程式碼應直接從 utils_io / utils_display / utils_text 匯入。
"""
from __future__ import annotations

from src.cli.utils_display import console as console
from src.cli.utils_io import (
    JSONStore as JSONStore,
    _cleanup_stale_atomic_tmps as _cleanup_stale_atomic_tmps,
    _copy_default as _copy_default,
    _looks_like_repo_root as _looks_like_repo_root,
    _normalize_state_path as _normalize_state_path,
    atomic_json_write as atomic_json_write,
    atomic_text_write as atomic_text_write,
    atomic_yaml_write as atomic_yaml_write,
    cleanup_orphan_tmps as cleanup_orphan_tmps,
    configure_state_dir as configure_state_dir,
    default_state_dir as default_state_dir,
    detect_state_dir as detect_state_dir,
    get_state_dir as get_state_dir,
    read_file_safe as read_file_safe,
    resolve_state_path as resolve_state_path,
    resolve_state_read_path as resolve_state_read_path,
    safe_config_write as safe_config_write,
    set_state_dir as set_state_dir,
)

__all__ = [
    "console",
    "JSONStore",
    "atomic_json_write",
    "atomic_text_write",
    "atomic_yaml_write",
    "cleanup_orphan_tmps",
    "configure_state_dir",
    "default_state_dir",
    "detect_state_dir",
    "get_state_dir",
    "read_file_safe",
    "resolve_state_path",
    "resolve_state_read_path",
    "safe_config_write",
    "set_state_dir",
]
