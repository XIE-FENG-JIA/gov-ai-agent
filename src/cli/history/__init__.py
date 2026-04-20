"""History CLI package."""

from __future__ import annotations

import typer

from ._shared import (
    _history_store,
    _pins_store,
    _tags_store,
    append_record,
    console,
    get_history_dir_path as _get_history_dir_path,
    get_pins_path as _get_pins_path,
    get_state_file_path as _get_state_file_path,
    get_tags_path as _get_tags_path,
    load_pins as _load_pins,
    load_tags as _load_tags,
    save_pins as _save_pins,
    save_tags as _save_tags,
)
from .archive import duplicate, history_archive, history_compare, rename
from .list import export_csv, export_history, history_clear, history_filter, history_list, history_search, history_stats
from .pin import pin, unpin
from .tag import tag_add, tag_list, tag_remove

app = typer.Typer()

app.command(name="list")(history_list)
app.command(name="export")(export_history)
app.command(name="export-csv")(export_csv)
app.command(name="stats")(history_stats)
app.command(name="search")(history_search)
app.command(name="clear")(history_clear)
app.command(name="filter")(history_filter)
app.command(name="tag-add")(tag_add)
app.command(name="tag-remove")(tag_remove)
app.command(name="tag-list")(tag_list)
app.command(name="duplicate")(duplicate)
app.command(name="rename")(rename)
app.command(name="pin")(pin)
app.command(name="unpin")(unpin)
app.command(name="archive")(history_archive)
app.command(name="compare")(history_compare)

__all__ = [
    "app",
    "append_record",
    "console",
    "duplicate",
    "export_csv",
    "export_history",
    "history_archive",
    "history_clear",
    "history_compare",
    "history_filter",
    "history_list",
    "history_search",
    "history_stats",
    "pin",
    "rename",
    "tag_add",
    "tag_list",
    "tag_remove",
    "unpin",
    "_get_history_dir_path",
    "_get_pins_path",
    "_get_state_file_path",
    "_get_tags_path",
    "_history_store",
    "_load_pins",
    "_load_tags",
    "_pins_store",
    "_save_pins",
    "_save_tags",
    "_tags_store",
]
