from __future__ import annotations

import json
from datetime import date
from unittest.mock import patch

from typer.testing import CliRunner

from src.sources.quality_config import QualityPolicy


runner = CliRunner()


class _FakeAdapter:
    def list(self, since_date=None, limit=10):
        return [{"id": "doc-1"}, {"id": "doc-2"}][:limit]

    def fetch(self, source_id: str):
        return {"id": source_id}

    def normalize(self, raw):
        return {
            "source_id": raw["id"],
            "source_url": f"https://example.gov/{raw['id']}",
            "source_agency": "測試機關",
            "source_doc_no": raw["id"],
            "source_date": "2026-04-20",
            "doc_type": "公告",
            "crawl_date": "2026-04-20",
            "content_md": f"# {raw['id']}",
            "synthetic": False,
            "fixture_fallback": False,
        }


def test_kb_gate_check_human_success() -> None:
    from src.cli.main import app

    with (
        patch("src.cli.kb.rebuild._adapter_registry", return_value={"mohw": _FakeAdapter}),
        patch("src.sources.quality_gate.get_quality_policy", return_value=QualityPolicy(expected_min_records=1)),
    ):
        result = runner.invoke(app, ["kb", "gate-check", "--source", "mohw", "--limit", "2"])

    assert result.exit_code == 0
    assert "quality gate: PASS" in result.stdout
    assert "adapter=mohw" in result.stdout
    assert "records_in=2 records_out=2" in result.stdout
    assert "pass_rate=1.00" in result.stdout


def test_kb_gate_check_json_success() -> None:
    from src.cli.main import app

    with (
        patch("src.cli.kb.rebuild._adapter_registry", return_value={"mohw": _FakeAdapter}),
        patch("src.sources.quality_gate.get_quality_policy", return_value=QualityPolicy(expected_min_records=1)),
    ):
        result = runner.invoke(
            app,
            ["kb", "gate-check", "--source", "mohw", "--format", "json", "--since", "2026-04-01"],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["adapter"] == "mohw"
    assert payload["records_in"] == 2
    assert payload["records_out"] == 2
    assert payload["pass_rate"] == 1.0


def test_kb_gate_check_passes_since_date_to_adapter() -> None:
    from src.cli.main import app

    class _SinceAdapter(_FakeAdapter):
        seen_since = None

        def list(self, since_date=None, limit=10):
            type(self).seen_since = since_date
            return super().list(since_date=since_date, limit=limit)

    with (
        patch("src.cli.kb.rebuild._adapter_registry", return_value={"mohw": _SinceAdapter}),
        patch("src.sources.quality_gate.get_quality_policy", return_value=QualityPolicy(expected_min_records=1)),
    ):
        result = runner.invoke(app, ["kb", "gate-check", "--source", "mohw", "--since", "2026-04-01"])

    assert result.exit_code == 0
    assert _SinceAdapter.seen_since == date(2026, 4, 1)


def test_kb_gate_check_json_failure_surfaces_named_error() -> None:
    from src.cli.main import app

    class _SyntheticAdapter(_FakeAdapter):
        def normalize(self, raw):
            payload = super().normalize(raw)
            payload["synthetic"] = True
            return payload

    with (
        patch("src.cli.kb.rebuild._adapter_registry", return_value={"mohw": _SyntheticAdapter}),
        patch("src.sources.quality_gate.get_quality_policy", return_value=QualityPolicy(expected_min_records=1)),
    ):
        result = runner.invoke(app, ["kb", "gate-check", "--source", "mohw", "--format", "json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["adapter"] == "mohw"
    assert payload["error_type"] == "SyntheticContamination"
    assert payload["record_id"] == "doc-1"
