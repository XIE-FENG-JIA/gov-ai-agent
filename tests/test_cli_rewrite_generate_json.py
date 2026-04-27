"""Tests for CLI JSON output mode — gov-ai rewrite & gov-ai generate (Epic 26 — T26.4)."""
import json
import os
import pytest
from typer.testing import CliRunner
from unittest.mock import MagicMock, patch

from src.cli.main import app

runner = CliRunner()


class TestRewriteJsonOutput:
    def test_rewrite_json_keys_present(self, tmp_path, monkeypatch):
        """rewrite --format json returns all required schema keys."""
        doc = tmp_path / "doc.txt"
        doc.write_text("主旨：測試公文改寫。\n說明：本文為測試用。\n", encoding="utf-8")
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "主旨：改寫後測試公文。\n說明：本文為改寫後測試用。"
        mock_config = MagicMock()
        mock_config.config = {"llm": {}}
        with patch("src.cli.rewrite_cmd.ConfigManager", return_value=mock_config), \
             patch("src.cli.rewrite_cmd.get_llm_factory", return_value=mock_llm):
            result = runner.invoke(app, ["rewrite", "--file", str(doc), "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert "rewritten" in data
        assert "doc_type" in data
        assert "score" in data
        assert "issues" in data

    def test_rewrite_json_schema_types(self, tmp_path):
        """rewrite --format json schema types are correct."""
        doc = tmp_path / "doc.txt"
        doc.write_text("主旨：測試。\n", encoding="utf-8")
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "改寫後的公文"
        mock_config = MagicMock()
        mock_config.config = {"llm": {}}
        with patch("src.cli.rewrite_cmd.ConfigManager", return_value=mock_config), \
             patch("src.cli.rewrite_cmd.get_llm_factory", return_value=mock_llm):
            result = runner.invoke(app, ["rewrite", "--file", str(doc), "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert isinstance(data["rewritten"], str)
        assert data["doc_type"] is None
        assert data["score"] is None
        assert isinstance(data["issues"], list)

    def test_rewrite_text_default_no_json(self, tmp_path):
        """rewrite default (text) output is not JSON."""
        doc = tmp_path / "doc.txt"
        doc.write_text("主旨：測試。\n", encoding="utf-8")
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "改寫後的公文"
        mock_config = MagicMock()
        mock_config.config = {"llm": {}}
        with patch("src.cli.rewrite_cmd.ConfigManager", return_value=mock_config), \
             patch("src.cli.rewrite_cmd.get_llm_factory", return_value=mock_llm):
            result = runner.invoke(app, ["rewrite", "--file", str(doc)])
        assert result.exit_code == 0, result.output
        with pytest.raises((json.JSONDecodeError, ValueError)):
            json.loads(result.stdout)

    def test_rewrite_invalid_format_exits_with_error(self, tmp_path):
        """rewrite --format invalid gives error message and exit 1."""
        doc = tmp_path / "doc.txt"
        doc.write_text("主旨：測試。\n", encoding="utf-8")
        result = runner.invoke(app, ["rewrite", "--file", str(doc), "--format", "xml"])
        assert result.exit_code == 1
        assert "xml" in result.output or "格式" in result.output

    def test_rewrite_json_rewritten_contains_llm_output(self, tmp_path):
        """rewrite --format json rewritten field contains LLM response."""
        doc = tmp_path / "doc.txt"
        doc.write_text("主旨：原始公文。\n", encoding="utf-8")
        expected = "主旨：LLM改寫結果。\n說明：測試通過。"
        mock_llm = MagicMock()
        mock_llm.generate.return_value = expected
        mock_config = MagicMock()
        mock_config.config = {"llm": {}}
        with patch("src.cli.rewrite_cmd.ConfigManager", return_value=mock_config), \
             patch("src.cli.rewrite_cmd.get_llm_factory", return_value=mock_llm):
            result = runner.invoke(app, ["rewrite", "--file", str(doc), "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert data["rewritten"] == expected


class TestGenerateJsonOutput:
    def _make_mock_runtime(self, doc_type="函", score=0.92):
        """Create a mock runtime module with minimal required methods."""
        requirement = MagicMock()
        requirement.doc_type = doc_type
        qa_report = MagicMock()
        qa_report.overall_score = score
        qa_report.risk_summary = "low"
        qa_report.rounds_used = 1
        runtime = MagicMock()
        runtime._resolve_input.return_value = "請生成一份函"
        runtime._init_pipeline.return_value = ({}, MagicMock(), MagicMock(), "請生成一份函")
        runtime._run_core_pipeline.return_value = (
            requirement, "草稿內容", qa_report, "QA報告文字", None, MagicMock(), MagicMock(), MagicMock()
        )
        runtime._apply_content_metadata.return_value = "草稿內容"
        runtime._export_document.return_value = "output.docx"
        runtime.time = MagicMock()
        runtime.time.monotonic.side_effect = [0.0, 5.0]
        runtime._display_summary.return_value = None
        runtime._display_format_options.return_value = None
        runtime.append_record.return_value = None
        return runtime

    def test_generate_json_keys_present(self, tmp_path, monkeypatch):
        """generate --format json returns all required schema keys."""
        monkeypatch.chdir(tmp_path)
        runtime = self._make_mock_runtime()
        with patch("src.cli.generate.cli._runtime", return_value=runtime):
            result = runner.invoke(app, ["generate", "--input", "請生成一份函", "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert "output" in data
        assert "doc_type" in data
        assert "score" in data
        assert "elapsed_sec" in data

    def test_generate_json_schema_types(self, tmp_path, monkeypatch):
        """generate --format json schema types are correct."""
        monkeypatch.chdir(tmp_path)
        runtime = self._make_mock_runtime(doc_type="公告", score=0.85)
        with patch("src.cli.generate.cli._runtime", return_value=runtime):
            result = runner.invoke(app, ["generate", "--input", "請生成一份公告", "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert isinstance(data["output"], str)
        assert isinstance(data["doc_type"], str)
        assert isinstance(data["score"], float)
        assert isinstance(data["elapsed_sec"], float)

    def test_generate_invalid_format_exits_with_error(self, tmp_path, monkeypatch):
        """generate --format invalid gives error message and exit 1."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["generate", "--input", "測試", "--format", "xml"])
        assert result.exit_code == 1
        assert "xml" in result.output or "格式" in result.output

    def test_generate_text_default_no_json(self, tmp_path, monkeypatch):
        """generate default (text) output is not JSON."""
        monkeypatch.chdir(tmp_path)
        runtime = self._make_mock_runtime()
        with patch("src.cli.generate.cli._runtime", return_value=runtime):
            result = runner.invoke(app, ["generate", "--input", "請生成一份函"])
        assert result.exit_code == 0, result.output
        with pytest.raises((json.JSONDecodeError, ValueError)):
            json.loads(result.stdout)
