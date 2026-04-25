from pathlib import Path

import typer
from rich.console import Console

from src.cli.shared.verify_service import (
    collect_citation_verification_checks,
    render_citation_verification_results,
)

console = Console()


def verify(
    file_path: str = typer.Argument(..., help="要驗證 citation metadata 的 .docx 檔案"),
) -> None:
    try:
        checks = collect_citation_verification_checks(Path(file_path))
    except FileNotFoundError:
        console.print(f"[red]錯誤：找不到檔案 {file_path}[/red]")
        raise typer.Exit(1)
    except ValueError as exc:
        console.print(f"[red]錯誤：{exc}[/red]")
        raise typer.Exit(1)

    passed, total = render_citation_verification_results(checks)
    if passed != total:
        raise typer.Exit(1)
