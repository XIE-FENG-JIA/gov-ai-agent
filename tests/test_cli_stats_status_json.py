"""Tests for CLI JSON output mode — gov-ai stats & gov-ai status (Epic 25 — T25.4)."""
import json

import pytest
from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


class TestStatsJsonOutput:
    def test_stats_json_keys_present(self, tmp_path, monkeypatch):
        """stats --format json contains all required schema keys."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["stats", "--format", "json"])
        assert result.exit_code == 0, result.stdout
        data = json.loads(result.stdout)
        assert "total" in data
        assert "success" in data
        assert "failed" in data
        assert "type_counts" in data
        assert "avg_score" in data

    def test_stats_json_empty_history(self, tmp_path, monkeypatch):
        """stats --format json with no history returns zeros."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["stats", "--format", "json"])
        assert result.exit_code == 0, result.stdout
        data = json.loads(result.stdout)
        assert data["total"] == 0
        assert data["success"] == 0
        assert data["failed"] == 0
        assert data["type_counts"] == {}
        assert data["avg_score"] is None

    def test_stats_json_with_history(self, tmp_path, monkeypatch):
        """stats --format json with history data reflects correct counts."""
        monkeypatch.chdir(tmp_path)
        history = [
            {"status": "success", "doc_type": "函", "score": 0.9},
            {"status": "success", "doc_type": "函", "score": 0.8},
            {"status": "failed", "doc_type": "公告", "score": None},
        ]
        (tmp_path / ".gov-ai-history.json").write_text(
            json.dumps(history, ensure_ascii=False), encoding="utf-8"
        )
        result = runner.invoke(app, ["stats", "--format", "json"])
        assert result.exit_code == 0, result.stdout
        data = json.loads(result.stdout)
        assert data["total"] == 3
        assert data["success"] == 2
        assert data["failed"] == 1
        assert data["type_counts"]["函"] == 2
        assert data["type_counts"]["公告"] == 1
        assert data["avg_score"] == pytest.approx(0.85, abs=1e-6)

    def test_stats_json_type_counts_is_dict(self, tmp_path, monkeypatch):
        """stats --format json type_counts is always a dict."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["stats", "--format", "json"])
        data = json.loads(result.stdout)
        assert isinstance(data["type_counts"], dict)

    def test_stats_text_default_not_json(self, tmp_path, monkeypatch):
        """Default text mode output is not raw JSON with schema keys."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["stats"])
        assert result.exit_code == 0
        try:
            data = json.loads(result.stdout)
            assert "total" not in data
        except (json.JSONDecodeError, ValueError):
            pass  # Plain rich text output — expected

    def test_stats_invalid_format_rejected(self, tmp_path, monkeypatch):
        """Invalid --format value gives clear error and non-zero exit code."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["stats", "--format", "csv"])
        assert result.exit_code != 0
        assert "不支援的輸出格式" in result.stdout or "csv" in result.stdout


class TestStatusJsonOutput:
    def test_status_json_keys_present(self, tmp_path, monkeypatch):
        """status --format json contains all required schema keys."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["status", "--format", "json"])
        assert result.exit_code == 0, result.stdout
        data = json.loads(result.stdout)
        assert "config" in data
        assert "history_count" in data
        assert "feedback_count" in data
        assert "kb_status" in data

    def test_status_json_no_files_returns_empty(self, tmp_path, monkeypatch):
        """status --format json with no files returns safe defaults."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["status", "--format", "json"])
        assert result.exit_code == 0, result.stdout
        data = json.loads(result.stdout)
        assert data["history_count"] == 0
        assert data["feedback_count"] == 0
        assert isinstance(data["config"], dict)
        assert isinstance(data["kb_status"], str)

    def test_status_json_with_history_and_feedback(self, tmp_path, monkeypatch):
        """status --format json counts reflect actual file contents."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gov-ai-history.json").write_text(
            json.dumps([{"id": "1"}, {"id": "2"}, {"id": "3"}], ensure_ascii=False),
            encoding="utf-8",
        )
        (tmp_path / ".gov-ai-feedback.json").write_text(
            json.dumps([{"score": 5}], ensure_ascii=False),
            encoding="utf-8",
        )
        result = runner.invoke(app, ["status", "--format", "json"])
        assert result.exit_code == 0, result.stdout
        data = json.loads(result.stdout)
        assert data["history_count"] == 3
        assert data["feedback_count"] == 1

    def test_status_json_config_reflects_yaml(self, tmp_path, monkeypatch):
        """status --format json config field mirrors config.yaml content."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text(
            "llm:\n  provider: openai\n  model: gpt-4\n", encoding="utf-8"
        )
        result = runner.invoke(app, ["status", "--format", "json"])
        assert result.exit_code == 0, result.stdout
        data = json.loads(result.stdout)
        assert data["config"].get("llm", {}).get("provider") == "openai"

    def test_status_text_default_not_json(self, tmp_path, monkeypatch):
        """Default text mode output cannot be parsed as JSON with schema keys."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        try:
            data = json.loads(result.stdout)
            assert "history_count" not in data
        except (json.JSONDecodeError, ValueError):
            pass  # Rich table output — expected

    def test_status_invalid_format_rejected(self, tmp_path, monkeypatch):
        """Invalid --format value for status gives clear error."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["status", "--format", "xml"])
        assert result.exit_code != 0
        assert "不支援的輸出格式" in result.stdout or "xml" in result.stdout
