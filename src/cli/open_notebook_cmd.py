from __future__ import annotations

import typer
from rich.console import Console

from src.integrations.open_notebook import (
    IntegrationDisabled,
    IntegrationSetupError,
    get_adapter,
)


app = typer.Typer(help="open-notebook integration smoke commands")
console = Console()


@app.command("smoke")
def smoke(
    question: str = typer.Option(..., "--question", help="Question for the smoke adapter."),
    doc: list[str] = typer.Option(
        None,
        "--doc",
        help="Optional evidence snippets to feed the smoke adapter.",
    ),
) -> None:
    """Exercise the repo-owned open-notebook seam without touching writer flow."""
    adapter = get_adapter()
    docs = [
        {
            "title": f"smoke-doc-{index}",
            "content_md": snippet,
        }
        for index, snippet in enumerate(doc or [], start=1)
    ]

    try:
        result = adapter.ask(question, docs)
    except (IntegrationDisabled, IntegrationSetupError) as exc:
        console.print(f"open-notebook smoke failed: {exc}")
        raise typer.Exit(code=2) from exc

    console.print(result.answer_text, markup=False)
    console.print(f"diagnostics: adapter={result.diagnostics.get('adapter', '?')}")
    console.print(f"evidence_count={len(result.evidence)}")
