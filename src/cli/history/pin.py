"""Pin commands for history records."""

from __future__ import annotations

import typer

from ._shared import console, load_pins, save_pins


def pin(
    record_id: str = typer.Argument(..., help="記錄 ID"),
) -> None:
    """釘選指定的歷史記錄。"""
    pins = load_pins()
    if record_id in pins:
        console.print(f"[yellow]記錄 {record_id} 已經是釘選狀態。[/yellow]")
        return
    pins.append(record_id)
    save_pins(pins)
    console.print(f"[green]已釘選記錄 {record_id}。[/green]")


def unpin(
    record_id: str = typer.Argument(..., help="記錄 ID"),
) -> None:
    """取消釘選指定的歷史記錄。"""
    pins = load_pins()
    if record_id not in pins:
        console.print(f"[yellow]記錄 {record_id} 未釘選。[/yellow]")
        return
    pins.remove(record_id)
    save_pins(pins)
    console.print(f"[green]已取消釘選記錄 {record_id}。[/green]")
