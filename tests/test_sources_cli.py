from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from src.sources.ingest import IngestRecord, SourceSnapshot


runner = CliRunner()


def test_sources_help_lists_ingest_command() -> None:
    from src.cli.main import app

    result = runner.invoke(app, ["sources", "--help"])

    assert result.exit_code == 0
    assert "ingest" in result.stdout
    assert "status" in result.stdout
    assert "stats" in result.stdout


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


def test_sources_status_command_shows_per_source_counts(tmp_path: Path) -> None:
    from src.cli.main import app

    snapshots = [
        SourceSnapshot(
            source_key="mojlaw",
            storage_name="mojlaw",
            raw_count=3,
            raw_bytes=120,
            corpus_count=2,
            latest_corpus_path=tmp_path / "corpus" / "mojlaw" / "law-002.md",
            latest_corpus_mtime=1713571200.0,
            last_crawl_mtime=1713571100.0,
        ),
        SourceSnapshot(
            source_key="fda",
            storage_name="fdaapi",
            raw_count=0,
            raw_bytes=0,
            corpus_count=0,
            latest_corpus_path=None,
            latest_corpus_mtime=None,
            last_crawl_mtime=None,
        ),
    ]

    with patch("src.cli.sources_cmd.collect_source_snapshots", return_value=snapshots):
        result = runner.invoke(app, ["sources", "status", "--base-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert "mojlaw: corpus=2 raw=3" in result.stdout
    assert "raw_bytes=120" in result.stdout
    assert "last_crawl=2024-04-20" in result.stdout
    assert "law-002.md" in result.stdout
    assert "fda: corpus=0 raw=0 raw_bytes=0 last_crawl=- latest=-" in result.stdout


def test_sources_stats_command_shows_aggregate_counts(tmp_path: Path) -> None:
    from src.cli.main import app

    snapshots = [
        SourceSnapshot(
            source_key="mojlaw",
            storage_name="mojlaw",
            raw_count=3,
            raw_bytes=120,
            corpus_count=2,
            latest_corpus_path=None,
            latest_corpus_mtime=None,
            last_crawl_mtime=None,
        ),
        SourceSnapshot(
            source_key="fda",
            storage_name="fdaapi",
            raw_count=1,
            raw_bytes=80,
            corpus_count=0,
            latest_corpus_path=None,
            latest_corpus_mtime=None,
            last_crawl_mtime=None,
        ),
    ]

    with patch("src.cli.sources_cmd.collect_source_snapshots", return_value=snapshots):
        result = runner.invoke(app, ["sources", "stats", "--base-dir", str(tmp_path)])

    assert result.exit_code == 0
    normalized_output = result.stdout.replace("\n", "")
    assert f"base_dir={tmp_path.as_posix()}".replace("/", "") in normalized_output.replace("/", "")
    assert "sources=2 active=2" in result.stdout
    assert "corpus=2 raw=4 raw_bytes=200" in result.stdout


def test_sources_stats_command_supports_single_adapter_breakdown(tmp_path: Path) -> None:
    from src.cli.main import app

    snapshots = [
        SourceSnapshot(
            source_key="mojlaw",
            storage_name="mojlaw",
            raw_count=3,
            raw_bytes=120,
            corpus_count=2,
            latest_corpus_path=None,
            latest_corpus_mtime=None,
            last_crawl_mtime=None,
        )
    ]

    with patch("src.cli.sources_cmd.collect_source_snapshots", return_value=snapshots):
        result = runner.invoke(app, ["sources", "stats", "--adapter", "mojlaw", "--base-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert "adapter=mojlaw storage=mojlaw" in result.stdout
    assert "corpus=2 raw=3 raw_bytes=120" in result.stdout
