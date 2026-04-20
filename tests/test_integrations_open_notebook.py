from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.integrations.open_notebook import (
    AskResult,
    IntegrationDisabled,
    OffAdapter,
    SmokeAdapter,
    WriterAdapter,
    get_adapter,
)


runner = CliRunner()


def test_get_adapter_supports_three_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "off")
    assert isinstance(get_adapter(), OffAdapter)

    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "smoke")
    assert isinstance(get_adapter(), SmokeAdapter)

    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "writer")
    assert isinstance(get_adapter(), WriterAdapter)


def test_off_adapter_raises_clear_error() -> None:
    adapter = OffAdapter()

    with pytest.raises(IntegrationDisabled, match="disabled"):
        adapter.ask("hi", ["doc"])


def test_smoke_adapter_returns_answer_and_first_doc_citation() -> None:
    adapter = SmokeAdapter()

    result = adapter.ask("hi", ["first doc", "second doc"])

    assert isinstance(result, AskResult)
    assert result.answer.startswith("[smoke] hi")
    assert result.citations[0].title == "smoke-doc-1"
    assert "first doc" in result.citations[0].snippet
    assert result.diagnostics["indexed_docs"] == "2"


def test_writer_mode_loudly_fails_when_vendor_is_missing() -> None:
    adapter = WriterAdapter(vendor_path=Path("vendor/open-notebook"))

    with pytest.raises(IntegrationDisabled, match="vendor/open-notebook"):
        adapter.ask("hi", ["doc"])


def test_open_notebook_smoke_cli_uses_smoke_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "smoke")

    from src.cli.main import app

    result = runner.invoke(app, ["open-notebook", "smoke", "--question", "hi"])

    assert result.exit_code == 0
    assert "[smoke] hi" in result.stdout
    assert "smoke-doc-1" in result.stdout


def test_open_notebook_smoke_cli_fails_loudly_in_writer_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "writer")

    from src.cli.main import app

    result = runner.invoke(app, ["open-notebook", "smoke", "--question", "hi"])

    assert result.exit_code == 2
    assert "open-notebook smoke failed" in result.stdout
    assert "vendor/open-notebook" in result.stdout
