from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

from scripts import live_ingest


def test_run_live_ingest_sets_force_live_and_collects_records(tmp_path: Path, monkeypatch) -> None:
    class FakeAdapter:
        pass

    observed: list[tuple[str, str | None]] = []

    def fake_ingest(adapter, *, limit, base_dir, require_live):  # type: ignore[no-untyped-def]
        observed.append((adapter.__class__.__name__, live_ingest.os.environ.get("GOV_AI_FORCE_LIVE")))
        assert limit == 2
        assert base_dir == tmp_path
        assert require_live is True
        corpus_path = tmp_path / "corpus" / "mojlaw" / "A0030018.md"
        corpus_path.parent.mkdir(parents=True, exist_ok=True)
        corpus_path.write_text(
            "---\n"
            "source_url: https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0030018\n"
            "synthetic: false\n"
            "fixture_fallback: false\n"
            "---\n"
            "# 公文程式條例\n\n第一句。第二句。\n",
            encoding="utf-8",
        )
        return [type("Record", (), {"corpus_path": corpus_path})()]

    monkeypatch.setattr(live_ingest, "_available_sources", lambda: {"mojlaw": FakeAdapter})
    monkeypatch.setattr(live_ingest, "_load_ingest_function", lambda: fake_ingest)

    results = live_ingest.run_live_ingest(source_keys=["mojlaw"], limit=2, base_dir=tmp_path)

    assert observed == [("FakeAdapter", "1")]
    assert "GOV_AI_FORCE_LIVE" not in live_ingest.os.environ
    assert results[0].status == "PASS"
    assert results[0].count == 1
    assert results[0].ingested_count == 1
    assert results[0].fixture_remaining == 0
    assert results[0].records[0]["synthetic"] is False
    assert results[0].records[0]["first_sentence"] == "公文程式條例 第一句"


def test_run_live_ingest_can_prune_fixture_backed_corpus(tmp_path: Path, monkeypatch) -> None:
    class FakeAdapter:
        pass

    def fake_ingest(adapter, *, limit, base_dir, require_live):  # type: ignore[no-untyped-def]
        corpus_root = base_dir / "corpus" / "mojlaw"
        corpus_root.mkdir(parents=True, exist_ok=True)
        (corpus_root / "live.md").write_text(
            "---\n"
            "source_url: https://example.test/live\n"
            "synthetic: false\n"
            "fixture_fallback: false\n"
            "---\n"
            "# Live doc\n\n真資料。\n",
            encoding="utf-8",
        )
        (corpus_root / "fixture.md").write_text(
            "---\n"
            "source_url: https://example.test/fixture\n"
            "synthetic: true\n"
            "fixture_fallback: true\n"
            "---\n"
            "# Fixture doc\n\n假資料。\n",
            encoding="utf-8",
        )
        return []

    monkeypatch.setattr(live_ingest, "_available_sources", lambda: {"mojlaw": FakeAdapter})
    monkeypatch.setattr(live_ingest, "_load_ingest_function", lambda: fake_ingest)

    results = live_ingest.run_live_ingest(
        source_keys=["mojlaw"],
        limit=2,
        base_dir=tmp_path,
        prune_fixture_fallback=True,
        archive_label="fixture_20260420",
    )

    assert results[0].status == "PASS"
    assert len(results[0].records) == 1
    assert results[0].ingested_count == 0
    assert results[0].fixture_remaining == 0
    assert results[0].archived_count == 1
    assert not (tmp_path / "corpus" / "mojlaw" / "fixture.md").exists()
    assert (tmp_path / "corpus" / "mojlaw" / "live.md").exists()
    assert (tmp_path / "archive" / "fixture_20260420" / "corpus" / "mojlaw" / "fixture.md").exists()


def test_run_live_ingest_ignores_archived_fixture_stub(tmp_path: Path, monkeypatch) -> None:
    class FakeAdapter:
        pass

    def fake_ingest(adapter, *, limit, base_dir, require_live):  # type: ignore[no-untyped-def]
        corpus_root = base_dir / "corpus" / "mojlaw"
        corpus_root.mkdir(parents=True, exist_ok=True)
        (corpus_root / "live.md").write_text(
            "---\n"
            "source_url: https://example.test/live\n"
            "synthetic: false\n"
            "fixture_fallback: false\n"
            "---\n"
            "# Live doc\n\n真資料。\n",
            encoding="utf-8",
        )
        return []

    def fake_archive_fixture_corpus(*, base_dir, storage_names, archive_label=None):  # type: ignore[no-untyped-def]
        corpus_root = base_dir / "corpus" / "mojlaw"
        (corpus_root / "fixture.md").write_text(
            "---\n"
            "source_url: https://example.test/fixture\n"
            "synthetic: true\n"
            "fixture_fallback: false\n"
            "deprecated: true\n"
            "archived_fixture: true\n"
            "---\n"
            "# Archived fixture corpus\n",
            encoding="utf-8",
        )
        return [object()]

    monkeypatch.setattr(live_ingest, "_available_sources", lambda: {"mojlaw": FakeAdapter})
    monkeypatch.setattr(live_ingest, "_load_ingest_function", lambda: fake_ingest)
    monkeypatch.setattr(live_ingest, "archive_fixture_corpus", fake_archive_fixture_corpus)

    results = live_ingest.run_live_ingest(
        source_keys=["mojlaw"],
        limit=2,
        base_dir=tmp_path,
        prune_fixture_fallback=True,
    )

    assert results[0].status == "PASS"
    assert len(results[0].records) == 1
    assert results[0].fixture_remaining == 0
    assert results[0].archived_count == 1
    assert len(results[0].records) == 1


def test_write_report_renders_markdown_table(tmp_path: Path) -> None:
    report_path = tmp_path / "docs" / "live-ingest-report.md"
    results = [
        live_ingest.SourceRunResult(
            source="mojlaw",
            status="PASS",
            count=1,
            summary="live_total=1 newly_ingested=1 fixture_remaining=0",
            records=[
                {
                    "source_url": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0030018",
                    "synthetic": False,
                    "fixture_fallback": False,
                    "archived_fixture": False,
                    "first_sentence": "公文程式條例 第一條",
                }
            ],
            ingested_count=1,
            fixture_remaining=0,
            archived_count=1,
            audit_records=[
                {
                    "source_url": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0030018",
                    "synthetic": False,
                    "fixture_fallback": False,
                    "deprecated": False,
                    "archived_fixture": False,
                    "first_sentence": "公文程式條例 第一條",
                }
            ],
        ),
        live_ingest.SourceRunResult(
            source="datagovtw",
            status="FAIL",
            count=0,
            summary="live ingest required",
            records=[],
            ingested_count=0,
            fixture_remaining=1,
            archived_count=0,
            audit_records=[
                {
                    "source_url": "https://example.test/fixture",
                    "synthetic": True,
                    "fixture_fallback": True,
                    "deprecated": False,
                    "archived_fixture": False,
                    "first_sentence": "Fixture only",
                }
            ],
        ),
    ]

    live_ingest.write_report(report_path, results=results, base_dir=tmp_path / "kb_data", limit=3, force_live=True)

    content = report_path.read_text(encoding="utf-8")
    assert "# Live Ingest Report" in content
    assert "- force_live: 1" in content
    assert "| source_url | synthetic | fixture_fallback | archived_fixture | first_sentence |" in content
    assert "live ingest required" in content
    assert "- live_count: 1" in content
    assert "- ingested_count: 1" in content
    assert "- archived_count: 1" in content
    assert "### retained_audit_evidence" in content
    assert "https://example.test/fixture" in content


def test_run_live_ingest_failure_keeps_fixture_audit_evidence(tmp_path: Path, monkeypatch) -> None:
    class FakeAdapter:
        pass

    def fake_ingest(adapter, *, limit, base_dir, require_live):  # type: ignore[no-untyped-def]
        raise RuntimeError("live ingest required for mojlaw")

    corpus_root = tmp_path / "corpus" / "mojlaw"
    corpus_root.mkdir(parents=True, exist_ok=True)
    (corpus_root / "fixture.md").write_text(
        "---\n"
        "source_url: https://example.test/fixture\n"
        "synthetic: true\n"
        "fixture_fallback: true\n"
        "---\n"
        "# Fixture doc\n\n假資料。\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(live_ingest, "_available_sources", lambda: {"mojlaw": FakeAdapter})
    monkeypatch.setattr(live_ingest, "_load_ingest_function", lambda: fake_ingest)

    results = live_ingest.run_live_ingest(source_keys=["mojlaw"], limit=1, base_dir=tmp_path)

    assert results[0].status == "FAIL"
    assert results[0].count == 0
    assert results[0].fixture_remaining == 1
    assert results[0].archived_count == 0
    assert len(results[0].audit_records) == 1
    assert results[0].audit_records[0]["fixture_fallback"] is True
    assert "retained_fixture=1" in results[0].summary


def test_main_reports_existing_real_corpus_when_no_new_docs_ingested(tmp_path: Path, monkeypatch) -> None:
    class FakeAdapter:
        pass

    def fake_ingest(adapter, *, limit, base_dir, require_live):  # type: ignore[no-untyped-def]
        corpus_root = base_dir / "corpus" / "mojlaw"
        corpus_root.mkdir(parents=True, exist_ok=True)
        (corpus_root / "existing-live.md").write_text(
            "---\n"
            "source_url: https://example.test/existing-live\n"
            "synthetic: false\n"
            "fixture_fallback: false\n"
            "---\n"
            "# Existing live doc\n\n既有真資料。\n",
            encoding="utf-8",
        )
        return []

    monkeypatch.setattr(live_ingest, "_available_sources", lambda: {"mojlaw": FakeAdapter})
    monkeypatch.setattr(live_ingest, "_load_ingest_function", lambda: fake_ingest)

    report_path = tmp_path / "docs" / "live-ingest-report.md"
    exit_code = live_ingest.main(
        [
            "--sources",
            "mojlaw",
            "--limit",
            "3",
            "--base-dir",
            str(tmp_path),
            "--report-path",
            str(report_path),
        ]
    )

    content = report_path.read_text(encoding="utf-8")
    assert exit_code == 0
    assert "- count: 1" in content
    assert "- live_count: 1" in content
    assert "- ingested_count: 0" in content


def test_run_live_ingest_ignores_malformed_corpus_files(tmp_path: Path, monkeypatch) -> None:
    class FakeAdapter:
        pass

    def fake_ingest(adapter, *, limit, base_dir, require_live):  # type: ignore[no-untyped-def]
        corpus_root = base_dir / "corpus" / "mojlaw"
        corpus_root.mkdir(parents=True, exist_ok=True)
        (corpus_root / "broken.md").write_text("probe\n", encoding="utf-8")
        (corpus_root / "live.md").write_text(
            "---\n"
            "source_url: https://example.test/live\n"
            "synthetic: false\n"
            "fixture_fallback: false\n"
            "---\n"
            "# Live doc\n\n真資料。\n",
            encoding="utf-8",
        )
        return []

    monkeypatch.setattr(live_ingest, "_available_sources", lambda: {"mojlaw": FakeAdapter})
    monkeypatch.setattr(live_ingest, "_load_ingest_function", lambda: fake_ingest)

    results = live_ingest.run_live_ingest(source_keys=["mojlaw"], limit=2, base_dir=tmp_path)

    assert results[0].status == "PASS"
    assert results[0].count == 1
    assert results[0].records[0]["source_url"] == "https://example.test/live"


def test_run_live_ingest_quality_gate_validates_active_live_rows(tmp_path: Path, monkeypatch) -> None:
    class FakeAdapter:
        pass

    def fake_ingest(adapter, *, limit, base_dir, require_live):  # type: ignore[no-untyped-def]
        corpus_root = base_dir / "corpus" / "mojlaw"
        corpus_root.mkdir(parents=True, exist_ok=True)
        (corpus_root / "A0001.md").write_text(
            "---\n"
            "source_id: A0001\n"
            "source_url: https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0001\n"
            "source_agency: 法務部全國法規資料庫\n"
            "source_doc_no: A0001\n"
            "source_date: 2026-04-20\n"
            "doc_type: 法規\n"
            "crawl_date: 2026-04-20\n"
            "synthetic: false\n"
            "fixture_fallback: false\n"
            "---\n"
            "# 測試法規\n\n真資料。\n",
            encoding="utf-8",
        )
        return []

    monkeypatch.setattr(live_ingest, "_available_sources", lambda: {"mojlaw": FakeAdapter})
    monkeypatch.setattr(live_ingest, "_load_ingest_function", lambda: fake_ingest)
    monkeypatch.setattr(
        "src.sources.quality_gate.get_quality_policy",
        lambda adapter_name: type(
            "Policy",
            (),
            {
                "expected_min_records": 1,
                "freshness_window_days": 365,
                "allow_fallback": False,
            },
        )(),
    )

    results = live_ingest.run_live_ingest(
        source_keys=["mojlaw"],
        limit=2,
        base_dir=tmp_path,
        quality_gate=True,
    )

    assert results[0].status == "PASS"
    assert "quality_gate=PASS" in results[0].summary
    assert "gate_records_in=1" in results[0].summary


def test_main_forwards_quality_gate_flag(tmp_path: Path, monkeypatch) -> None:
    observed: list[bool] = []

    monkeypatch.setattr(live_ingest, "_available_sources", lambda: {"mojlaw": object})
    monkeypatch.setattr(
        live_ingest,
        "run_live_ingest",
        lambda *,
        source_keys,
        limit,
        base_dir,
        require_live=True,
        prune_fixture_fallback=False,
        archive_label=None,
        quality_gate=False: observed.append(quality_gate) or [],
    )
    monkeypatch.setattr(live_ingest, "write_report", lambda *args, **kwargs: None)

    exit_code = live_ingest.main(["--sources", "mojlaw", "--base-dir", str(tmp_path), "--quality-gate"])

    assert exit_code == 0
    assert observed == [True]


def test_main_rejects_unknown_source(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(live_ingest, "_available_sources", lambda: {"mojlaw": object})

    try:
        live_ingest.main(["--sources", "unknown", "--base-dir", str(tmp_path)])
    except SystemExit as exc:
        assert exc.code == 2
    else:  # pragma: no cover
        raise AssertionError("expected parser to exit on unknown source")


def test_main_accepts_underscored_source_alias(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(live_ingest, "_available_sources", lambda: {"executive_yuan_rss": object})
    monkeypatch.setattr(
        live_ingest,
        "run_live_ingest",
        lambda *, source_keys, limit, base_dir, require_live=True, prune_fixture_fallback=False, archive_label=None:
        calls.append(source_keys) or [],
    )
    monkeypatch.setattr(live_ingest, "write_report", lambda *args, **kwargs: None)

    exit_code = live_ingest.main(["--sources", "executiveyuanrss", "--base-dir", str(tmp_path)])

    assert exit_code == 0
    assert calls == [["executive_yuan_rss"]]


def test_main_accepts_explicit_require_live_flag(tmp_path: Path, monkeypatch) -> None:
    observed: list[bool] = []

    monkeypatch.setattr(live_ingest, "_available_sources", lambda: {"mojlaw": object})
    monkeypatch.setattr(
        live_ingest,
        "run_live_ingest",
        lambda *,
        source_keys,
        limit,
        base_dir,
        require_live=True,
        prune_fixture_fallback=False,
        archive_label=None: observed.append(require_live) or [],
    )
    monkeypatch.setattr(live_ingest, "write_report", lambda *args, **kwargs: None)

    exit_code = live_ingest.main(["--sources", "mojlaw", "--base-dir", str(tmp_path), "--require-live"])

    assert exit_code == 0
    assert observed == [True]


def test_cli_help_runs_as_script_entrypoint() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/live_ingest.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--prune-fixture-fallback" in result.stdout
