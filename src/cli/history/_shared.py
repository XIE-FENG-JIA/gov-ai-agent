"""Shared state and helpers for history commands."""

from __future__ import annotations

import os
from datetime import datetime

import typer
from rich.console import Console

from src.cli.utils_io import JSONStore, atomic_json_write, resolve_state_path, resolve_state_read_path
from src.core.history_store import _history_store, append_record

console = Console()
_TAGS_FILE = os.path.join(".history", "tags.json")
_PINS_FILE = os.path.join(".history", "pins.json")
_ARCHIVE_EXCLUDE = {"tags.json", "pins.json"}

_tags_store = JSONStore(_TAGS_FILE, default={})
_pins_store = JSONStore(_PINS_FILE, default=[])


def get_state_file_path(relative_path: str, *, for_write: bool) -> str:
    if not for_write:
        return resolve_state_read_path(relative_path)
    read_path = resolve_state_read_path(relative_path)
    write_path = resolve_state_path(relative_path)
    if read_path != write_path and os.path.isfile(read_path) and not os.path.exists(write_path):
        return read_path
    return write_path


def get_history_dir_path(*, for_write: bool) -> str:
    if not for_write:
        return resolve_state_read_path(".history")
    read_path = resolve_state_read_path(".history")
    write_path = resolve_state_path(".history")
    if read_path != write_path and os.path.isdir(read_path) and not os.path.exists(write_path):
        return read_path
    return write_path


def get_tags_path(*, for_write: bool = False) -> str:
    return get_state_file_path(_TAGS_FILE, for_write=for_write)


def load_tags() -> dict[str, list[str]]:
    path = get_tags_path()
    if os.path.isfile(path):
        try:
            return _tags_store.load()
        except (OSError, TypeError):
            return {}
    return {}


def save_tags(tags: dict[str, list[str]]) -> None:
    atomic_json_write(get_tags_path(for_write=True), tags)


def get_pins_path(*, for_write: bool = False) -> str:
    return get_state_file_path(_PINS_FILE, for_write=for_write)


def load_pins() -> list[str]:
    path = get_pins_path()
    if os.path.isfile(path):
        try:
            return _pins_store.load()
        except (OSError, TypeError):
            return []
    return []


def save_pins(pins: list[str]) -> None:
    atomic_json_write(get_pins_path(for_write=True), pins)


def parse_date(value: str, *, field_label: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        console.print(f"[red]{field_label}格式錯誤，請使用 YYYY-MM-DD。[/red]")
        raise typer.Exit(1) from exc
