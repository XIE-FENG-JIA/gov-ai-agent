from __future__ import annotations

from pathlib import Path

import yaml

from scripts import live_ingest


def test_run_live_ingest_sets_force_live_and_collects_records(tmp_path: Path, monkeypatch) -> None:
    class FakeAdapter:
        pass

    observed: list[tuple[str, str | None]] = []

    def fake_registry():  # type: ignore[no-untyped-def]
        return {"mojlaw": FakeAdapter}

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

    monkeypatch.setattr(live_ingest, "_adapter_registry", fake_registry)
    monkeypatch.setattr(live_ingest, "ingest", fake_ingest)

    results = live_ingest.run_live_ingest(source_keys=["mojlaw"], limit=2, base_dir=tmp_path)

    assert observed == [("FakeAdapter", "1")]
    assert "GOV_AI_FORCE_LIVE" not in live_ingest.os.environ
    assert results[0].status == "PASS"
    assert results[0].count == 1
    assert results[0].records[0]["synthetic"] is False
    assert results[0].records[0]["first_sentence"] == "公文程式條例 第一句"


def test_write_report_renders_markdown_table(tmp_path: Path) -> None:
    report_path = tmp_path / "docs" / "live-ingest-report.md"
    results = [
        live_ingest.SourceRunResult(
            source="mojlaw",
            status="PASS",
            count=1,
            summary="ingested=1",
            records=[
                {
                    "source_url": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0030018",
                    "synthetic": False,
                    "fixture_fallback": False,
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
        ),
    ]

    live_ingest.write_report(report_path, results=results, base_dir=tmp_path / "kb_data", limit=3)

    content = report_path.read_text(encoding="utf-8")
    assert "# Live Ingest Report" in content
    assert "| source_url | synthetic | fixture_fallback | first_sentence |" in content
    assert "live ingest required" in content
    assert "- count: 1" in content


def test_main_rejects_unknown_source(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(live_ingest, "_adapter_registry", lambda: {"mojlaw": object})

    try:
        live_ingest.main(["--sources", "unknown", "--base-dir", str(tmp_path)])
    except SystemExit as exc:
        assert exc.code == 2
    else:  # pragma: no cover
        raise AssertionError("expected parser to exit on unknown source")
