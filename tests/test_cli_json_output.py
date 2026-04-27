"""Tests for CLI JSON output mode (Epic 24 — T24.5)."""
import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


class TestLintJsonOutput:
    def test_lint_json_keys_present(self, tmp_path):
        """JSON mode output contains required keys: issues, score, pass."""
        doc = tmp_path / "ok.txt"
        doc.write_text("主旨：本件辦理完畢，查照。\n說明：如前所述。", encoding="utf-8")
        result = runner.invoke(app, ["lint", "-f", str(doc), "--format", "json"])
        data = json.loads(result.stdout)
        assert "issues" in data
        assert "score" in data
        assert "pass" in data

    def test_lint_json_no_issues_score_one(self, tmp_path):
        """No issues → score=1.0, pass=True, exit_code=0."""
        doc = tmp_path / "ok.txt"
        doc.write_text("主旨：本件辦理完畢，查照。\n說明：如前所述。", encoding="utf-8")
        result = runner.invoke(app, ["lint", "-f", str(doc), "--format", "json"])
        data = json.loads(result.stdout)
        assert data["score"] == 1.0
        assert data["pass"] is True
        assert result.exit_code == 0

    def test_lint_json_with_issues_pass_false(self, tmp_path):
        """Issues present → pass=False, score<1.0, exit_code=1."""
        doc = tmp_path / "bad.txt"
        doc.write_text("所以需要辦理，但是這個問題很重要。", encoding="utf-8")
        result = runner.invoke(app, ["lint", "-f", str(doc), "--format", "json"])
        data = json.loads(result.stdout)
        assert len(data["issues"]) > 0
        assert data["pass"] is False
        assert data["score"] < 1.0
        assert result.exit_code == 1

    def test_lint_json_issues_are_list(self, tmp_path):
        """JSON mode issues field is always a list."""
        doc = tmp_path / "ok.txt"
        doc.write_text("主旨：查照。\n說明：無。", encoding="utf-8")
        result = runner.invoke(app, ["lint", "-f", str(doc), "--format", "json"])
        data = json.loads(result.stdout)
        assert isinstance(data["issues"], list)

    def test_lint_text_default_not_json(self, tmp_path):
        """Default text mode output cannot be parsed as JSON dict with keys."""
        doc = tmp_path / "ok.txt"
        doc.write_text("主旨：本件辦理完畢，查照。\n說明：如前所述。", encoding="utf-8")
        result = runner.invoke(app, ["lint", "-f", str(doc)])
        # Text output should not be valid JSON with the expected keys
        try:
            data = json.loads(result.stdout)
            assert "issues" not in data
        except (json.JSONDecodeError, ValueError):
            pass  # Plain text output — expected

    def test_lint_invalid_format_rejected(self, tmp_path):
        """Invalid --format value gives clear error and non-zero exit code."""
        doc = tmp_path / "ok.txt"
        doc.write_text("主旨：查照。\n說明：無。", encoding="utf-8")
        result = runner.invoke(app, ["lint", "-f", str(doc), "--format", "xlsx"])
        assert result.exit_code != 0
        assert "不支援的輸出格式" in result.stdout or "xlsx" in result.stdout


class TestCiteJsonOutput:
    @patch("src.cli.cite_cmd._load_mapping")
    @patch("src.cli.cite_cmd._detect_doc_type")
    def test_cite_json_keys_present(self, mock_detect, mock_load, tmp_path):
        """cite --format json output contains citations and count keys."""
        mock_detect.return_value = "函"
        mock_load.return_value = {
            "公文程式條例": {
                "applicable_doc_types": ["函"],
                "pcode": "A0040002",
                "description": "公文程式規範",
                "source_level": "A",
            }
        }
        draft = tmp_path / "draft.md"
        draft.write_text("受文者：某機關\n主旨：查照", encoding="utf-8")
        result = runner.invoke(app, ["cite", str(draft), "--format", "json"])
        assert result.exit_code == 0, result.stdout
        data = json.loads(result.stdout)
        assert "citations" in data
        assert "count" in data
        assert isinstance(data["citations"], list)
        assert data["count"] == len(data["citations"])

    @patch("src.cli.cite_cmd._load_mapping")
    @patch("src.cli.cite_cmd._detect_doc_type")
    def test_cite_invalid_format_rejected(self, mock_detect, mock_load, tmp_path):
        """cite with invalid --format gives error."""
        mock_detect.return_value = "函"
        mock_load.return_value = {}
        draft = tmp_path / "draft.md"
        draft.write_text("受文者：某機關\n主旨：查照", encoding="utf-8")
        result = runner.invoke(app, ["cite", str(draft), "--format", "xml"])
        assert result.exit_code != 0


class TestVerifyJsonOutput:
    @patch("src.cli.verify_cmd.collect_citation_verification_checks")
    def test_verify_json_keys_verdict_pass(self, mock_checks, tmp_path):
        """verify --format json contains facts and verdict=pass when all checks pass."""
        mock_checks.return_value = [
            ("metadata.citation_count", True, "2 vs 2"),
            ("metadata.engine", True, "gov-ai-v1"),
        ]
        docx = tmp_path / "doc.docx"
        docx.write_bytes(b"PK fake")
        result = runner.invoke(app, ["verify", str(docx), "--format", "json"])
        data = json.loads(result.stdout)
        assert "facts" in data
        assert "verdict" in data
        assert data["verdict"] == "pass"
        assert result.exit_code == 0

    @patch("src.cli.verify_cmd.collect_citation_verification_checks")
    def test_verify_json_verdict_fail(self, mock_checks, tmp_path):
        """verify --format json verdict=fail when all checks fail, exit_code=1."""
        mock_checks.return_value = [
            ("metadata.citation_count", False, "1 vs 2"),
        ]
        docx = tmp_path / "doc.docx"
        docx.write_bytes(b"PK fake")
        result = runner.invoke(app, ["verify", str(docx), "--format", "json"])
        data = json.loads(result.stdout)
        assert data["verdict"] == "fail"
        assert result.exit_code == 1

    @patch("src.cli.verify_cmd.collect_citation_verification_checks")
    def test_verify_json_verdict_warn(self, mock_checks, tmp_path):
        """verify --format json verdict=warn when some checks pass and some fail."""
        mock_checks.return_value = [
            ("metadata.citation_count", True, "2 vs 2"),
            ("citation[1] doc-1", False, "找不到對應 repo evidence"),
        ]
        docx = tmp_path / "doc.docx"
        docx.write_bytes(b"PK fake")
        result = runner.invoke(app, ["verify", str(docx), "--format", "json"])
        data = json.loads(result.stdout)
        assert data["verdict"] == "warn"
        assert result.exit_code == 1

    @patch("src.cli.verify_cmd.collect_citation_verification_checks")
    def test_verify_json_facts_structure(self, mock_checks, tmp_path):
        """verify --format json facts items contain check, ok, detail keys."""
        mock_checks.return_value = [
            ("metadata.engine", True, "gov-ai-v1"),
        ]
        docx = tmp_path / "doc.docx"
        docx.write_bytes(b"PK fake")
        result = runner.invoke(app, ["verify", str(docx), "--format", "json"])
        data = json.loads(result.stdout)
        fact = data["facts"][0]
        assert "check" in fact
        assert "ok" in fact
        assert "detail" in fact


class TestKbSearchJsonOutput:
    @patch("src.cli.kb.KnowledgeBaseManager")
    @patch("src.cli.kb.get_llm_factory")
    @patch("src.cli.kb.ConfigManager")
    def test_kb_search_json_keys_present(self, mock_cm, mock_factory, mock_kb_class):
        """kb search --format json output contains results and count keys."""
        mock_cm.return_value.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./test_kb"},
        }
        mock_kb_instance = mock_kb_class.return_value
        mock_kb_instance.is_available = True
        mock_kb_instance.search_hybrid.return_value = [
            {
                "metadata": {"title": "公文程式條例", "doc_type": "法規", "source_level": "A"},
                "content": "第一條 公文之種類如下：",
                "distance": 0.2,
            }
        ]
        result = runner.invoke(app, ["kb", "search", "公文", "--format", "json"])
        assert result.exit_code == 0, result.stdout
        data = json.loads(result.stdout)
        assert "results" in data
        assert "count" in data
        assert data["count"] == 1
        item = data["results"][0]
        assert "doc_id" in item
        assert "score" in item
        assert "snippet" in item

    @patch("src.cli.kb.KnowledgeBaseManager")
    @patch("src.cli.kb.get_llm_factory")
    @patch("src.cli.kb.ConfigManager")
    def test_kb_search_json_empty_results(self, mock_cm, mock_factory, mock_kb_class):
        """kb search --format json with no results returns count=0."""
        mock_cm.return_value.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./test_kb"},
        }
        mock_kb_instance = mock_kb_class.return_value
        mock_kb_instance.is_available = True
        mock_kb_instance.search_hybrid.return_value = []
        result = runner.invoke(app, ["kb", "search", "公文", "--format", "json"])
        assert result.exit_code == 0, result.stdout
        data = json.loads(result.stdout)
        assert data["count"] == 0
        assert data["results"] == []

    @patch("src.cli.kb.KnowledgeBaseManager")
    @patch("src.cli.kb.get_llm_factory")
    @patch("src.cli.kb.ConfigManager")
    def test_kb_search_invalid_format_rejected(self, mock_cm, mock_factory, mock_kb_class):
        """kb search with invalid --format gives error."""
        mock_cm.return_value.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./test_kb"},
        }
        mock_kb_instance = mock_kb_class.return_value
        mock_kb_instance.is_available = True
        result = runner.invoke(app, ["kb", "search", "公文", "--format", "csv"])
        assert result.exit_code != 0
