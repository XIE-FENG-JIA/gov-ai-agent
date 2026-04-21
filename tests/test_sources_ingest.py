from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
import requests
import yaml

from src.core.models import PublicGovDoc
from src.sources.base import BaseSourceAdapter
from src.sources.ingest import FixtureFallbackError, build_argument_parser, collect_source_snapshots, ingest, main


class FakeAdapter(BaseSourceAdapter):
    def __init__(self) -> None:
        self._payloads = {
            "DOC-001": {"id": "DOC-001", "title": "測試法規一", "body": "第一份內容"},
            "DOC-002": {"id": "DOC-002", "title": "測試法規二", "body": "第二份內容"},
        }

    def list(self, since_date: date | None = None, limit: int = 3):  # type: ignore[override]
        docs = [
            {"id": "DOC-001", "title": "測試法規一", "date": date(2026, 4, 20)},
            {"id": "DOC-002", "title": "測試法規二", "date": date(2026, 4, 19)},
        ]
        if since_date is not None:
            docs = [doc for doc in docs if doc["date"] >= since_date]
        return docs[:limit]

    def fetch(self, doc_id: str) -> dict[str, str]:
        return self._payloads[doc_id]

    def normalize(self, raw: dict[str, str]) -> PublicGovDoc:
        return PublicGovDoc(
            source_id=raw["id"],
            source_url=f"https://example.gov/{raw['id']}",
            source_agency="測試機關",
            source_doc_no=raw["id"],
            source_date=date(2026, 4, 20),
            doc_type="法規",
            raw_snapshot_path=None,
            crawl_date=date(2026, 4, 20),
            content_md=f"# {raw['title']}\n\n{raw['body']}",
            synthetic=False,
        )


def test_ingest_writes_raw_and_corpus_files(tmp_path: Path) -> None:
    records = ingest(FakeAdapter(), limit=2, base_dir=tmp_path)

    assert len(records) == 2
    raw_payload = json.loads(records[0].raw_path.read_text(encoding="utf-8"))
    assert raw_payload["id"] == "DOC-001"

    content = records[0].corpus_path.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    _sep, raw_meta, body = content.split("---\n", 2)
    metadata = yaml.safe_load(raw_meta)

    assert metadata["title"] == "測試法規一"
    assert metadata["source_id"] == "DOC-001"
    assert metadata["raw_snapshot_path"].endswith("kb_data\\raw\\fake\\202604\\DOC-001.json") is False
    assert metadata["raw_snapshot_path"].endswith("DOC-001.json")
    assert metadata["synthetic"] is False
    assert metadata["fixture_fallback"] is False
    assert body.strip().startswith("# 測試法規一")


def test_ingest_deduplicates_existing_source_id(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus" / "fake"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "DOC-001.md").write_text("---\ntitle: existing\n---\nold", encoding="utf-8")

    records = ingest(FakeAdapter(), limit=2, base_dir=tmp_path)

    assert [record.source_id for record in records] == ["DOC-002"]
    assert not (tmp_path / "raw" / "fake" / "202604" / "DOC-001.json").exists()


def test_ingest_upgrades_fixture_backed_corpus_when_live_doc_becomes_available(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus" / "fake"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "DOC-001.md").write_text(
        "---\n"
        "title: 測試法規一\n"
        "synthetic: true\n"
        "fixture_fallback: true\n"
        "---\n"
        "# 舊 fixture 版本\n",
        encoding="utf-8",
    )

    records = ingest(FakeAdapter(), limit=1, base_dir=tmp_path)

    assert [record.source_id for record in records] == ["DOC-001"]
    content = (corpus_dir / "DOC-001.md").read_text(encoding="utf-8")
    metadata = yaml.safe_load(content.split("---\n", 2)[1])
    assert metadata["synthetic"] is False
    assert metadata["fixture_fallback"] is False
    assert "# 測試法規一" in content
    assert "第一份內容" in content
    assert (tmp_path / "raw" / "fake" / "202604" / "DOC-001.json").exists()


def test_ingest_keeps_fixture_backed_corpus_when_only_fixture_data_is_available(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus" / "fixtureonly"
    corpus_dir.mkdir(parents=True)
    original = (
        "---\n"
        "title: 測試法規一\n"
        "synthetic: true\n"
        "fixture_fallback: true\n"
        "---\n"
        "# 舊 fixture 版本\n"
    )
    target = corpus_dir / "DOC-001.md"
    target.write_text(original, encoding="utf-8")

    class FixtureOnlyAdapter(FakeAdapter):
        def normalize(self, raw: dict[str, str]) -> PublicGovDoc:
            doc = super().normalize(raw)
            return doc.model_copy(update={"synthetic": True, "fixture_fallback": True})

    records = ingest(FixtureOnlyAdapter(), limit=1, base_dir=tmp_path)

    assert records == []
    assert target.read_text(encoding="utf-8") == original
    assert not (tmp_path / "raw" / "fixtureonly" / "202604" / "DOC-001.json").exists()


def test_main_uses_registry_and_prints_written_paths(tmp_path: Path, monkeypatch, capsys) -> None:
    from src.sources import ingest as ingest_module

    class FakeCliAdapter(FakeAdapter):
        pass

    monkeypatch.setattr(ingest_module, "_adapter_registry", lambda: {"mojlaw": FakeCliAdapter})

    exit_code = main(["--source", "mojlaw", "--limit", "1", "--base-dir", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "ingested=1 source=mojlaw" in captured.out
    assert "DOC-001.md" in captured.out


def test_main_passes_require_live_flag_to_ingest(tmp_path: Path, monkeypatch) -> None:
    from src.sources import ingest as ingest_module

    class FakeCliAdapter(FakeAdapter):
        pass

    observed: dict[str, object] = {}

    def fake_ingest(adapter, **kwargs):  # type: ignore[no-untyped-def]
        observed["adapter"] = adapter
        observed.update(kwargs)
        return []

    monkeypatch.setattr(ingest_module, "_adapter_registry", lambda: {"mojlaw": FakeCliAdapter})
    monkeypatch.setattr(ingest_module, "ingest", fake_ingest)

    exit_code = main(["--source", "mojlaw", "--limit", "1", "--base-dir", str(tmp_path), "--require-live"])

    assert exit_code == 0
    assert isinstance(observed["adapter"], FakeCliAdapter)
    assert observed["require_live"] is True


def test_build_argument_parser_includes_rss_and_api_sources() -> None:
    parser = build_argument_parser()

    source_action = next(action for action in parser._actions if action.dest == "source")

    assert "executive_yuan_rss" in source_action.choices
    assert "executiveyuanrss" in source_action.choices
    assert "fda" in source_action.choices
    assert "mohw" in source_action.choices
    assert "pcc" in source_action.choices


def test_main_mojlaw_cli_falls_back_to_local_fixtures(tmp_path: Path, capsys) -> None:
    with patch(
        "src.sources.mojlaw.requests.Session.get",
        side_effect=requests.ConnectionError("offline for fixture fallback"),
    ):
        exit_code = main(["--source", "mojlaw", "--limit", "3", "--base-dir", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "ingested=3 source=mojlaw" in captured.out
    written = list((tmp_path / "corpus" / "mojlaw").glob("*.md"))
    assert len(written) == 3
    metadata = yaml.safe_load(written[0].read_text(encoding="utf-8").split("---\n", 2)[1])
    assert metadata["synthetic"] is True
    assert metadata["fixture_fallback"] is True


def test_main_mojlaw_cli_require_live_fails_on_fixture_fallback(tmp_path: Path, capsys) -> None:
    with patch(
        "src.sources.mojlaw.requests.Session.get",
        side_effect=requests.ConnectionError("offline for fixture fallback"),
    ):
        exit_code = main(["--source", "mojlaw", "--limit", "3", "--base-dir", str(tmp_path), "--require-live"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "error=live ingest required for mojlaw" in captured.out
    assert list((tmp_path / "corpus" / "mojlaw").glob("*.md")) == []


def test_ingest_require_live_rejects_fixture_fallback(tmp_path: Path) -> None:
    class FixtureOnlyAdapter(FakeAdapter):
        def normalize(self, raw: dict[str, str]) -> PublicGovDoc:
            doc = super().normalize(raw)
            return doc.model_copy(update={"synthetic": True, "fixture_fallback": True})

    with pytest.raises(FixtureFallbackError, match="live ingest required"):
        ingest(FixtureOnlyAdapter(), limit=1, base_dir=tmp_path, require_live=True)

    assert not (tmp_path / "raw" / "fixtureonly").exists()
    assert list((tmp_path / "corpus" / "fixtureonly").glob("*.md")) == []


def test_collect_source_snapshots_reads_existing_storage_dirs(tmp_path: Path) -> None:
    (tmp_path / "raw" / "mojlaw" / "202604").mkdir(parents=True)
    (tmp_path / "corpus" / "mojlaw").mkdir(parents=True)
    (tmp_path / "raw" / "mojlaw" / "202604" / "DOC-001.json").write_text("{}", encoding="utf-8")
    latest = tmp_path / "corpus" / "mojlaw" / "DOC-002.md"
    latest.write_text("# doc", encoding="utf-8")

    snapshots = collect_source_snapshots(base_dir=tmp_path)

    mojlaw = next(snapshot for snapshot in snapshots if snapshot.source_key == "mojlaw")
    assert mojlaw.storage_name == "mojlaw"
    assert mojlaw.raw_count == 1
    assert mojlaw.raw_bytes == 2
    assert mojlaw.corpus_count == 1
    assert mojlaw.latest_corpus_path == latest
    assert mojlaw.last_crawl_mtime is not None
