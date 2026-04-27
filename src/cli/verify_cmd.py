import json as _json
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
    output_format: str = typer.Option("text", "--format", help="輸出格式：text（預設）或 json"),
) -> None:
    if output_format not in {"text", "json"}:
        console.print(f"[red]錯誤：不支援的輸出格式 '{output_format}'，請使用 text 或 json。[/red]")
        raise typer.Exit(1)
    try:
        checks = collect_citation_verification_checks(Path(file_path))
    except FileNotFoundError:
        console.print(f"[red]錯誤：找不到檔案 {file_path}[/red]")
        raise typer.Exit(1)
    except ValueError as exc:
        console.print(f"[red]錯誤：{exc}[/red]")
        raise typer.Exit(1)

    if output_format == "json":
        facts = [{"check": name, "ok": ok, "detail": detail} for name, ok, detail in checks]
        passed = sum(1 for _, ok, _ in checks if ok)
        total = len(checks)
        if passed == total:
            verdict = "pass"
        elif passed == 0:
            verdict = "fail"
        else:
            verdict = "warn"
        print(_json.dumps({"facts": facts, "verdict": verdict}, ensure_ascii=False))
        if passed != total:
            raise typer.Exit(1)
        return

    passed, total = render_citation_verification_results(checks)
    if passed != total:
        raise typer.Exit(1)
