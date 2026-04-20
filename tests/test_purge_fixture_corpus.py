from __future__ import annotations

from pathlib import Path

from scripts import purge_fixture_corpus


def test_archive_fixture_corpus_moves_fixture_markdown_and_raw(tmp_path: Path) -> None:
    base_dir = tmp_path / "kb_data"
    corpus_path = base_dir / "corpus" / "mojlaw" / "fixture.md"
    raw_path = base_dir / "raw" / "mojlaw" / "202604" / "fixture.json"
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text('{"id": "fixture"}', encoding="utf-8")
    corpus_path.write_text(
        "---\n"
        "raw_snapshot_path: kb_data\\raw\\mojlaw\\202604\\fixture.json\n"
        "fixture_fallback: true\n"
        "---\n"
        "# Fixture doc\n",
        encoding="utf-8",
    )
    live_path = base_dir / "corpus" / "mojlaw" / "live.md"
    live_path.write_text(
        "---\n"
        "raw_snapshot_path: kb_data\\raw\\mojlaw\\202604\\live.json\n"
        "fixture_fallback: false\n"
        "---\n"
        "# Live doc\n",
        encoding="utf-8",
    )

    archived = purge_fixture_corpus.archive_fixture_corpus(
        base_dir=base_dir,
        storage_names=["mojlaw"],
        archive_label="fixture_20260420",
    )

    assert len(archived) == 1
    assert not corpus_path.exists()
    assert not raw_path.exists()
    assert live_path.exists()
    assert (base_dir / "archive" / "fixture_20260420" / "corpus" / "mojlaw" / "fixture.md").exists()
    assert (base_dir / "archive" / "fixture_20260420" / "raw" / "mojlaw" / "202604" / "fixture.json").exists()


def test_main_prints_archive_summary(tmp_path: Path, capsys) -> None:
    base_dir = tmp_path / "kb_data"
    corpus_path = base_dir / "corpus" / "datagovtw" / "fixture.md"
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    corpus_path.write_text("---\nfixture_fallback: true\n---\n# Fixture\n", encoding="utf-8")

    exit_code = purge_fixture_corpus.main(
        ["--base-dir", str(base_dir), "--storage-name", "datagovtw", "--archive-label", "fixture_20260420"]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "archived=1" in captured.out
    assert "fixture_20260420" in captured.out
