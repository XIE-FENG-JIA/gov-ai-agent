from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from src.sources.ingest import IngestRecord


runner = CliRunner()


def test_sources_help_lists_ingest_command() -> None:
    from src.cli.main import app

    result = runner.invoke(app, ["sources", "--help"])

    assert result.exit_code == 0
    assert "ingest" in result.stdout


def test_sources_ingest_command_wires_main_cli(tmp_path: Path) -> None:
    from src.cli.main import app

    expected_records = [
        IngestRecord(
            source_id="law-001",
            raw_path=tmp_path / "raw" / "mojlaw" / "202604" / "law-001.json",
            corpus_path=tmp_path / "corpus" / "mojlaw" / "law-001.md",
        )
    ]

    class FakeAdapter:
        pass

    with (
        patch("src.cli.sources_cmd._adapter_registry", return_value={"mojlaw": FakeAdapter}),
        patch("src.cli.sources_cmd.run_ingest", return_value=expected_records) as mock_run_ingest,
    ):
        result = runner.invoke(
            app,
            ["sources", "ingest", "--source", "mojlaw", "--since", "2026-04-01", "--limit", "1", "--base-dir", str(tmp_path)],
        )

    assert result.exit_code == 0
    assert "完成" in result.stdout
    assert "law-001.md" in result.stdout
    mock_run_ingest.assert_called_once()

    adapter = mock_run_ingest.call_args.args[0]
    assert isinstance(adapter, FakeAdapter)
    assert mock_run_ingest.call_args.kwargs["since_date"] == date(2026, 4, 1)
    assert mock_run_ingest.call_args.kwargs["limit"] == 1
    assert mock_run_ingest.call_args.kwargs["base_dir"] == tmp_path


def test_sources_ingest_rejects_bad_date() -> None:
    from src.cli.main import app

    result = runner.invoke(app, ["sources", "ingest", "--source", "mojlaw", "--since", "2026/04/01"])

    assert result.exit_code != 0
    assert "YYYY-MM-DD" in (result.stderr or "")
