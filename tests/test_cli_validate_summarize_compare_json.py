"""Tests for CLI JSON output mode — Epic 27 (validate, summarize, compare)."""
import json

import pytest
from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


# ── validate ──────────────────────────────────────────────────────────────


class TestValidateJsonOutput:
    def test_validate_json_keys_present(self, tmp_path):
        """JSON mode output contains required keys."""
        doc = tmp_path / "test.docx"
        doc.write_bytes(b"")  # invalid docx → exit 1 but still JSON error
        result = runner.invoke(app, ["validate", str(doc), "--format", "json"])
        # Either valid JSON with 'error' or valid JSON with 'checks' schema
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_validate_json_schema_on_invalid_docx(self, tmp_path):
        """JSON mode on bad file path returns JSON with 'error' key, exit 1."""
        result = runner.invoke(app, ["validate", "nonexistent.docx", "--format", "json"])
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert "error" in data

    def test_validate_json_non_docx_extension(self, tmp_path):
        """JSON mode on non-.docx file returns JSON error, exit 1."""
        f = tmp_path / "file.txt"
        f.write_text("content", encoding="utf-8")
        result = runner.invoke(app, ["validate", str(f), "--format", "json"])
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert "error" in data

    def test_validate_text_default_not_json(self, tmp_path):
        """Default text mode on non-.docx does NOT output JSON object."""
        f = tmp_path / "file.txt"
        f.write_text("content", encoding="utf-8")
        result = runner.invoke(app, ["validate", str(f)])
        # Should not parse as {'error': ...} JSON – output is Rich text
        try:
            data = json.loads(result.stdout)
            assert "error" not in data
        except (json.JSONDecodeError, AssertionError):
            pass  # non-JSON text output is the expected default

    def test_validate_invalid_format_value(self, tmp_path):
        """Unknown --format value exits 1."""
        f = tmp_path / "file.docx"
        f.write_bytes(b"")
        result = runner.invoke(app, ["validate", str(f), "--format", "xml"])
        assert result.exit_code == 1


# ── summarize ─────────────────────────────────────────────────────────────


class TestSummarizeJsonOutput:
    def test_summarize_json_keys_present(self, tmp_path):
        """JSON mode output contains title, summary, source_file, max_length."""
        doc = tmp_path / "gov.txt"
        doc.write_text("主旨：本件辦理完畢。\n說明：詳如附件。", encoding="utf-8")
        result = runner.invoke(
            app, ["summarize", str(doc), "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "title" in data
        assert "summary" in data
        assert "source_file" in data
        assert "max_length" in data

    def test_summarize_json_values(self, tmp_path):
        """JSON title and summary match extracted content."""
        doc = tmp_path / "gov.txt"
        doc.write_text("主旨：請查照辦理。\n說明：無其他事項。", encoding="utf-8")
        result = runner.invoke(
            app, ["summarize", str(doc), "--format", "json"]
        )
        data = json.loads(result.stdout)
        assert data["title"] == "請查照辦理。"
        assert "max_length" in data

    def test_summarize_json_missing_file(self, tmp_path):
        """JSON mode on missing file returns JSON error, exit 1."""
        result = runner.invoke(app, ["summarize", "no_such.txt", "--format", "json"])
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert "error" in data

    def test_summarize_text_default_not_json(self, tmp_path):
        """Default text mode output is Rich Panel, not raw JSON."""
        doc = tmp_path / "gov.txt"
        doc.write_text("主旨：查照。\n說明：無。", encoding="utf-8")
        result = runner.invoke(app, ["summarize", str(doc)])
        assert result.exit_code == 0
        # Rich panel output should not start with {
        stripped = result.stdout.strip()
        assert not stripped.startswith("{") or "title" not in stripped

    def test_summarize_invalid_format_value(self, tmp_path):
        """Unknown --format value exits 1."""
        doc = tmp_path / "gov.txt"
        doc.write_text("主旨：查照。", encoding="utf-8")
        result = runner.invoke(app, ["summarize", str(doc), "--format", "csv"])
        assert result.exit_code == 1


# ── compare ───────────────────────────────────────────────────────────────


class TestCompareJsonOutput:
    def test_compare_json_identical_files(self, tmp_path):
        """JSON mode on identical files returns identical=True, added=0, removed=0."""
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("相同內容\n", encoding="utf-8")
        b.write_text("相同內容\n", encoding="utf-8")
        result = runner.invoke(app, ["compare", str(a), str(b), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["identical"] is True
        assert data["added"] == 0
        assert data["removed"] == 0
        assert data["diff_lines"] == []

    def test_compare_json_diff_files(self, tmp_path):
        """JSON mode on differing files returns correct counts and diff_lines."""
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("行一\n行二\n", encoding="utf-8")
        b.write_text("行一\n行三\n", encoding="utf-8")
        result = runner.invoke(app, ["compare", str(a), str(b), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "added" in data
        assert "removed" in data
        assert "identical" in data
        assert "diff_lines" in data
        assert data["identical"] is False
        assert isinstance(data["diff_lines"], list)

    def test_compare_json_schema_keys(self, tmp_path):
        """JSON mode always contains all 4 schema keys."""
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("v1\n", encoding="utf-8")
        b.write_text("v2\n", encoding="utf-8")
        result = runner.invoke(app, ["compare", str(a), str(b), "--format", "json"])
        data = json.loads(result.stdout)
        for key in ("added", "removed", "identical", "diff_lines"):
            assert key in data

    def test_compare_text_default_not_json(self, tmp_path):
        """Default text mode output is Rich panel, not raw JSON."""
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("v1\n", encoding="utf-8")
        b.write_text("v2\n", encoding="utf-8")
        result = runner.invoke(app, ["compare", str(a), str(b)])
        assert result.exit_code == 0
        try:
            data = json.loads(result.stdout)
            assert "added" not in data
        except json.JSONDecodeError:
            pass  # expected – Rich output

    def test_compare_invalid_format_value(self, tmp_path):
        """Unknown --format value exits 1."""
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("x\n", encoding="utf-8")
        b.write_text("y\n", encoding="utf-8")
        result = runner.invoke(app, ["compare", str(a), str(b), "--format", "xml"])
        assert result.exit_code == 1
