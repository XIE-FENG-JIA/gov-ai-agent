from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from src.sources.quality_config import QualityPolicy


runner = CliRunner()


def _write_corpus_doc(path, *, synthetic: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "title: 測試文件\n"
        "source_id: A0001\n"
        "source_url: https://example.gov/A0001\n"
        "source_agency: 測試機關\n"
        "source_doc_no: A0001\n"
        "source_date: 2026-04-20\n"
        "doc_type: 法規\n"
        "crawl_date: 2026-04-20\n"
        f"synthetic: {'true' if synthetic else 'false'}\n"
        "fixture_fallback: false\n"
        "---\n"
        "# 測試文件\n"
        "內容\n",
        encoding="utf-8",
    )


@patch("src.cli.kb.KnowledgeBaseManager")
@patch("src.cli.kb.get_llm_factory")
@patch("src.cli.kb.ConfigManager")
def test_kb_rebuild_quality_gate_rebuilds_active_corpus(
    mock_cm,
    mock_factory,
    mock_kb_class,
    tmp_path,
) -> None:
    from src.cli.main import app

    mock_cm.return_value.config = {
        "llm": {"provider": "mock"},
        "knowledge_base": {"path": "./test_kb"},
    }
    mock_kb_instance = mock_kb_class.return_value
    mock_kb_instance.get_stats.return_value = {
        "examples_count": 0,
        "regulations_count": 1,
        "policies_count": 0,
    }
    mock_kb_instance.contextual_retrieval = False
    mock_kb_instance.upsert_document.return_value = "law-1"

    _write_corpus_doc(tmp_path / "corpus" / "mojlaw" / "A0001.md")

    with patch("src.sources.quality_gate.get_quality_policy", return_value=QualityPolicy(expected_min_records=1)):
        result = runner.invoke(app, ["kb", "rebuild", "--base-dir", str(tmp_path), "--quality-gate"])

    assert result.exit_code == 0
    mock_kb_instance.reset_db.assert_called_once()
    assert mock_kb_instance.upsert_document.call_count == 1
    assert "quality gate: PASS" in result.stdout
    assert "adapter=mojlaw records_in=1 records_out=1" in result.stdout
    assert "only-real 模式：以 active corpus" in result.stdout
    assert "為唯一重建來源" in result.stdout


@patch("src.cli.kb.KnowledgeBaseManager")
@patch("src.cli.kb.get_llm_factory")
@patch("src.cli.kb.ConfigManager")
def test_kb_rebuild_quality_gate_aborts_on_named_failure(
    mock_cm,
    mock_factory,
    mock_kb_class,
    tmp_path,
) -> None:
    from src.cli.main import app

    mock_cm.return_value.config = {
        "llm": {"provider": "mock"},
        "knowledge_base": {"path": "./test_kb"},
    }
    mock_kb_instance = mock_kb_class.return_value
    mock_kb_instance.get_stats.return_value = {
        "examples_count": 0,
        "regulations_count": 0,
        "policies_count": 0,
    }
    mock_kb_instance.contextual_retrieval = False

    _write_corpus_doc(tmp_path / "corpus" / "mojlaw" / "A0001.md", synthetic=True)
    _write_corpus_doc(tmp_path / "corpus" / "datagovtw" / "doc-1.md")

    with patch("src.sources.quality_gate.get_quality_policy", return_value=QualityPolicy(expected_min_records=1)):
        result = runner.invoke(app, ["kb", "rebuild", "--base-dir", str(tmp_path), "--quality-gate"])

    assert result.exit_code == 1
    assert mock_kb_instance.upsert_document.call_count == 0
    assert '"error_type": "SyntheticContamination"' in result.stderr
    assert '"adapter": "mojlaw"' in result.stderr
    assert "datagovtw" not in result.stdout
