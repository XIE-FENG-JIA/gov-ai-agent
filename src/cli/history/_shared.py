"""Shared state and helpers for history commands."""

from __future__ import annotations

import os
from datetime import datetime

import typer
from rich.console import Console

from src.cli.utils_io import JSONStore, atomic_json_write, resolve_state_path, resolve_state_read_path

console = Console()
_MAX_HISTORY = 100
_TAGS_FILE = os.path.join(".history", "tags.json")
_PINS_FILE = os.path.join(".history", "pins.json")
_ARCHIVE_EXCLUDE = {"tags.json", "pins.json"}

_history_store = JSONStore(".gov-ai-history.json", default=[])
_tags_store = JSONStore(_TAGS_FILE, default={})
_pins_store = JSONStore(_PINS_FILE, default=[])


def append_record(
    input_text: str,
    doc_type: str,
    output_path: str,
    score: float | None = None,
    risk: str | None = None,
    rounds_used: int | None = None,
    elapsed: float | None = None,
    status: str = "success",
) -> None:
    """Append one history record."""
    record = {
        "timestamp": datetime.now().isoformat(),
        "input": input_text[:200],
        "doc_type": doc_type,
        "output": output_path,
        "score": score,
        "risk": risk,
        "rounds_used": rounds_used,
        "elapsed_sec": round(elapsed, 1) if elapsed else None,
        "status": status,
    }
    history = _history_store.load()
    history.append(record)
    if len(history) > _MAX_HISTORY:
        history = history[-_MAX_HISTORY:]

    try:
        _history_store.save(history)
    except OSError:
        pass


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
