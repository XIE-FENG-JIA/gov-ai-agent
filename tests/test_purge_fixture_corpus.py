from __future__ import annotations

import shutil
from pathlib import Path

import yaml

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


def test_archive_fixture_corpus_moves_malformed_probe(tmp_path: Path) -> None:
    base_dir = tmp_path / "kb_data"
    bad_path = base_dir / "corpus" / "mojlaw" / "A0030018.md"
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text("probe\n", encoding="utf-8")

    archived = purge_fixture_corpus.archive_fixture_corpus(
        base_dir=base_dir,
        storage_names=["mojlaw"],
        archive_label="fixture_20260420",
    )

    assert len(archived) == 1
    assert not bad_path.exists()
    assert (base_dir / "archive" / "fixture_20260420" / "corpus" / "mojlaw" / "A0030018.md").exists()


def test_archive_fixture_corpus_uses_collision_safe_name(tmp_path: Path) -> None:
    base_dir = tmp_path / "kb_data"
    corpus_path = base_dir / "corpus" / "mojlaw" / "A0030018.md"
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    corpus_path.write_text(
        "---\n"
        "raw_snapshot_path: kb_data\\raw\\mojlaw\\202604\\A0030018.json\n"
        "fixture_fallback: true\n"
        "---\n"
        "# Fixture doc\n",
        encoding="utf-8",
    )
    archive_target = base_dir / "archive" / "fixture_20260420" / "corpus" / "mojlaw" / "A0030018.md"
    archive_target.parent.mkdir(parents=True, exist_ok=True)
    archive_target.write_text("probe\n", encoding="utf-8")

    archived = purge_fixture_corpus.archive_fixture_corpus(
        base_dir=base_dir,
        storage_names=["mojlaw"],
        archive_label="fixture_20260420",
    )

    assert len(archived) == 1
    assert archived[0].corpus_target.name == "A0030018.dup1.md"
    assert (archive_target.parent / "A0030018.dup1.md").exists()


def test_archive_fixture_corpus_falls_back_to_copy_and_stub_on_permission_error(tmp_path: Path, monkeypatch) -> None:
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
        "synthetic: true\n"
        "---\n"
        "# Fixture doc\n",
        encoding="utf-8",
    )

    original_move = shutil.move

    def deny_move(source: str, target: str):  # type: ignore[no-untyped-def]
        if source.endswith("fixture.md") or source.endswith("fixture.json"):
            raise PermissionError("delete denied")
        return original_move(source, target)

    monkeypatch.setattr(purge_fixture_corpus.shutil, "move", deny_move)

    archived = purge_fixture_corpus.archive_fixture_corpus(
        base_dir=base_dir,
        storage_names=["mojlaw"],
        archive_label="fixture_20260420",
    )

    assert len(archived) == 1
    assert corpus_path.exists()
    metadata = yaml.safe_load(corpus_path.read_text(encoding="utf-8").split("---\n", 2)[1])
    assert metadata["deprecated"] is True
    assert metadata["archived_fixture"] is True
    assert metadata["fixture_fallback"] is False
    assert (base_dir / "archive" / "fixture_20260420" / "corpus" / "mojlaw" / "fixture.md").exists()
    assert (base_dir / "archive" / "fixture_20260420" / "raw" / "mojlaw" / "202604" / "fixture.json").exists()
    assert raw_path.exists()


def test_archive_fixture_corpus_is_idempotent_when_archive_target_exists(tmp_path: Path) -> None:
    base_dir = tmp_path / "kb_data"
    corpus_path = base_dir / "corpus" / "mojlaw" / "fixture.md"
    archive_path = base_dir / "archive" / "fixture_20260420" / "corpus" / "mojlaw" / "fixture.md"
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    content = "---\nfixture_fallback: true\n---\n# Fixture\n"
    corpus_path.write_text(content, encoding="utf-8")
    archive_path.write_text(content, encoding="utf-8")

    archived = purge_fixture_corpus.archive_fixture_corpus(
        base_dir=base_dir,
        storage_names=["mojlaw"],
        archive_label="fixture_20260420",
    )

    assert len(archived) == 1
    assert not corpus_path.exists()
    assert archive_path.exists()
