from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.integrations.open_notebook import (
    IntegrationDisabled,
    IntegrationSetupError,
    OpenNotebookAdapter,
    get_adapter,
    probe_vendor_runtime,
)


runner = CliRunner()


def test_probe_vendor_runtime_detects_git_stub(tmp_path: Path) -> None:
    vendor_path = tmp_path / "open-notebook"
    (vendor_path / ".git").mkdir(parents=True)

    is_ready, reason = probe_vendor_runtime(vendor_path)

    assert is_ready is False
    assert "only .git metadata" in reason


def test_probe_vendor_runtime_detects_incomplete_git_checkout(tmp_path: Path) -> None:
    vendor_path = tmp_path / "open-notebook"
    git_dir = vendor_path / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "config.lock").write_text("", encoding="utf-8")
    (git_dir / "description").write_text("incomplete clone\n", encoding="utf-8")

    is_ready, reason = probe_vendor_runtime(vendor_path)

    assert is_ready is False
    assert "vendor checkout is incomplete" in reason
    assert "config.lock" in reason
    assert "HEAD" in reason


def test_get_adapter_defaults_to_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOV_AI_OPEN_NOTEBOOK_MODE", raising=False)

    adapter = get_adapter()

    assert isinstance(adapter, OpenNotebookAdapter)
    with pytest.raises(IntegrationDisabled):
        adapter.ask("hi")


def test_probe_vendor_runtime_supports_importable_checkout(tmp_path: Path) -> None:
    vendor_path = tmp_path / "open-notebook"
    package_dir = vendor_path / "open_notebook"
    package_dir.mkdir(parents=True)
    (vendor_path / "pyproject.toml").write_text("[project]\nname='open-notebook'\n", encoding="utf-8")
    (package_dir / "__init__.py").write_text("__version__ = '1.8.5'\n", encoding="utf-8")

    is_ready, reason = probe_vendor_runtime(vendor_path)

    assert is_ready is True
    assert "imported open_notebook successfully" in reason
    assert "version=1.8.5" in reason


def test_probe_vendor_runtime_reports_missing_dependency(tmp_path: Path) -> None:
    vendor_path = tmp_path / "open-notebook"
    package_dir = vendor_path / "open_notebook"
    package_dir.mkdir(parents=True)
    (vendor_path / "pyproject.toml").write_text("[project]\nname='open-notebook'\n", encoding="utf-8")
    (package_dir / "__init__.py").write_text("import missing_open_notebook_dep\n", encoding="utf-8")

    is_ready, reason = probe_vendor_runtime(vendor_path)

    assert is_ready is False
    assert "vendor runtime import failed" in reason
    assert "missing=missing_open_notebook_dep" in reason


def test_get_adapter_returns_smoke_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "smoke")

    adapter = get_adapter()
    result = adapter.ask(
        "hi",
        [{"title": "Doc A", "content_md": "alpha", "source_url": "https://example.test/a"}],
    )

    assert isinstance(adapter, OpenNotebookAdapter)
    assert result.answer_text
    assert result.evidence[0].title == "Doc A"
    assert result.diagnostics["adapter"] == "smoke"


def test_get_adapter_writer_mode_fails_loudly_without_vendor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    vendor_path = tmp_path / "open-notebook"
    (vendor_path / ".git").mkdir(parents=True)
    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "writer")
    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_VENDOR_PATH", str(vendor_path))

    with pytest.raises(IntegrationSetupError) as exc_info:
        get_adapter()

    assert "writer mode requires a usable vendor/open-notebook checkout" in str(exc_info.value)
    assert "only .git metadata" in str(exc_info.value)


def test_open_notebook_help_lists_smoke_command() -> None:
    from src.cli.main import app

    result = runner.invoke(app, ["open-notebook", "--help"])

    assert result.exit_code == 0
    assert "smoke" in result.stdout


def test_open_notebook_smoke_command_returns_nonempty_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.cli.main import app

    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "smoke")
    result = runner.invoke(
        app,
        ["open-notebook", "smoke", "--question", "hi", "--doc", "first evidence"],
    )

    assert result.exit_code == 0
    assert "[open-notebook smoke] hi" in result.stdout
    assert "evidence_count=1" in result.stdout


def test_open_notebook_smoke_command_fails_when_mode_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.cli.main import app

    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "off")
    result = runner.invoke(app, ["open-notebook", "smoke", "--question", "hi"])

    assert result.exit_code == 2
    assert "open-notebook smoke failed" in result.stdout
