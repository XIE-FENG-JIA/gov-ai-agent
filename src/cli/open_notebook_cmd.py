"""CLI smoke path for the repo-owned open-notebook seam."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from src.integrations.open_notebook import IntegrationDisabled, get_adapter


app = typer.Typer(help="open-notebook seam smoke tools")
console = Console()


def _load_docs(doc_paths: list[Path] | None) -> list[str]:
    if not doc_paths:
        return ["Gov AI smoke doc: this seam preserves answer text and evidence payloads."]
    return [path.read_text(encoding="utf-8") for path in doc_paths]


@app.command("smoke")
def smoke_command(
    question: str = typer.Option(..., "--question", "-q", help="Ask-style smoke question"),
    doc: list[Path] | None = typer.Option(None, "--doc", exists=True, dir_okay=False, readable=True, help="Optional UTF-8 text docs"),
    mode: str | None = typer.Option(None, "--mode", help="Override GOV_AI_OPEN_NOTEBOOK_MODE for this command"),
) -> None:
    """Run the repo-owned smoke adapter without touching the production writer."""
    try:
        adapter = get_adapter(mode)
        docs = _load_docs(doc)
        adapter.index(docs)
        result = adapter.ask(question, docs)
    except (IntegrationDisabled, OSError, UnicodeDecodeError, ValueError) as exc:
        console.print(f"[red]open-notebook smoke failed[/red] {exc}")
        raise typer.Exit(code=2) from exc

    console.print(result.answer)
    for idx, citation in enumerate(result.citations, 1):
        console.print(f"[{idx}] {citation.title}: {citation.snippet}")

