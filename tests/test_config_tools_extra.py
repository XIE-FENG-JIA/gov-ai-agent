"""config_tools.py 未覆蓋分支補測（82% → 95%+）

覆蓋 Missing lines: 62-63, 73, 212-213, 333-399, 405, 407, 440-442, 479, 500
"""
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
import yaml
from typer.testing import CliRunner

runner = CliRunner()


# ---------------------------------------------------------------------------
# show 命令：不支援的格式 (L62-63)
# ---------------------------------------------------------------------------
class TestShowEdgeCases:
    @patch("src.cli.config_tools.ConfigManager")
    def test_show_unsupported_format(self, mock_cm):
        from src.cli.config_tools import app as config_app
        result = runner.invoke(config_app, ["show", "--format", "xml"])
        assert result.exit_code != 0
        assert "不支援的格式" in result.output

    @patch("src.cli.config_tools.ConfigManager")
    def test_show_section_json_format(self, mock_cm):
        """show --section llm --format json → L73 覆蓋"""
        mock_cm.return_value.config = {
            "llm": {"provider": "ollama", "model": "llama3.1:8b"}
        }
        from src.cli.config_tools import app as config_app
        result = runner.invoke(config_app, ["show", "--section", "llm", "--format", "json"])
        assert result.exit_code == 0
        assert '"llm"' in result.output
        assert '"provider"' in result.output

    @patch("src.cli.config_tools.ConfigManager")
    def test_show_section_non_dict_value(self, mock_cm):
        """section 值非 dict 時走空 dict 分支 (L76)"""
        mock_cm.return_value.config = {
            "debug": True
        }
        from src.cli.config_tools import app as config_app
        result = runner.invoke(config_app, ["show", "--section", "debug"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# fetch_models：Timeout / ConnectionError (L212-213)
# ---------------------------------------------------------------------------
class TestFetchModelsErrors:
    @patch("src.cli.config_tools.requests.get")
    @patch("src.cli.config_tools.ConfigManager")
    def test_fetch_models_timeout(self, mock_cm, mock_get):
        import requests as req
        mock_cm.return_value.config = {"providers": {"openrouter": {"api_key": "k"}}}
        mock_get.side_effect = req.Timeout("timeout")
        from src.cli.config_tools import app as config_app
        result = runner.invoke(config_app, ["fetch-models"])
        assert result.exit_code != 0
        assert "逾時" in result.output

    @patch("src.cli.config_tools.requests.get")
    @patch("src.cli.config_tools.ConfigManager")
    def test_fetch_models_connection_error(self, mock_cm, mock_get):
        import requests as req
        mock_cm.return_value.config = {"providers": {"openrouter": {"api_key": "k"}}}
        mock_get.side_effect = req.ConnectionError("refused")
        from src.cli.config_tools import app as config_app
        result = runner.invoke(config_app, ["fetch-models"])
        assert result.exit_code != 0
        assert "無法連線" in result.output


# ---------------------------------------------------------------------------
# init 命令 (L333-399) — 互動式引導
# ---------------------------------------------------------------------------
class TestConfigInit:
    @patch("src.cli.config_tools.Prompt.ask")
    @patch("src.cli.config_tools.Confirm.ask", return_value=False)
    def test_init_existing_file_cancel(self, mock_confirm, mock_prompt, tmp_path, monkeypatch):
        """config.yaml 已存在、使用者取消 → Exit"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  provider: ollama\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        from src.cli.config_tools import app as config_app
        result = runner.invoke(config_app, ["init"])
        assert "已取消" in result.output

    @patch("src.cli.config_tools.Prompt.ask")
    def test_init_ollama_new(self, mock_prompt, tmp_path, monkeypatch):
        """從零建立 ollama config"""
        monkeypatch.chdir(tmp_path)
        # choice=1 (ollama), model=llama3.1:8b, kb_path=./kb_data
        mock_prompt.side_effect = ["1", "llama3.1:8b", "./kb_data"]
        from src.cli.config_tools import app as config_app
        result = runner.invoke(config_app, ["init"])
        assert "設定檔已建立" in result.output
        created = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
        assert created["llm"]["provider"] == "ollama"

    @patch("src.cli.config_tools.Prompt.ask")
    def test_init_gemini(self, mock_prompt, tmp_path, monkeypatch):
        """gemini provider 路徑"""
        monkeypatch.chdir(tmp_path)
        mock_prompt.side_effect = ["2", "./kb"]
        from src.cli.config_tools import app as config_app
        result = runner.invoke(config_app, ["init"])
        assert "設定檔已建立" in result.output
        created = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
        assert created["llm"]["provider"] == "gemini"

    @patch("src.cli.config_tools.Prompt.ask")
    def test_init_openrouter(self, mock_prompt, tmp_path, monkeypatch):
        """openrouter provider 路徑"""
        monkeypatch.chdir(tmp_path)
        mock_prompt.side_effect = ["3", "./kb"]
        from src.cli.config_tools import app as config_app
        result = runner.invoke(config_app, ["init"])
        assert "設定檔已建立" in result.output
        created = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
        assert created["llm"]["provider"] == "openrouter"

    @patch("src.cli.config_tools.Prompt.ask")
    @patch("src.cli.config_tools.Confirm.ask", return_value=True)
    def test_init_overwrite_existing(self, mock_confirm, mock_prompt, tmp_path, monkeypatch):
        """config.yaml 已存在、使用者確認覆蓋"""
        (tmp_path / "config.yaml").write_text("old: data\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        mock_prompt.side_effect = ["1", "llama3.1:8b", "./kb"]
        from src.cli.config_tools import app as config_app
        result = runner.invoke(config_app, ["init"])
        assert "設定檔已建立" in result.output

    @patch("src.cli.config_tools.Prompt.ask")
    def test_init_gemini_env_detected(self, mock_prompt, tmp_path, monkeypatch):
        """gemini 且偵測到環境變數"""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
        mock_prompt.side_effect = ["2", "./kb"]
        from src.cli.config_tools import app as config_app
        result = runner.invoke(config_app, ["init"])
        assert "設定檔已建立" in result.output


# ---------------------------------------------------------------------------
# _parse_value：布林 True/False (L405, 407)
# ---------------------------------------------------------------------------
class TestParseValue:
    def test_parse_true(self):
        from src.cli.config_tools import _parse_value
        assert _parse_value("true") is True
        assert _parse_value("yes") is True
        assert _parse_value("YES") is True

    def test_parse_false(self):
        from src.cli.config_tools import _parse_value
        assert _parse_value("false") is False
        assert _parse_value("no") is False
        assert _parse_value("NO") is False

    def test_parse_float(self):
        from src.cli.config_tools import _parse_value
        assert _parse_value("0.7") == 0.7
        assert _parse_value("3.14") == 3.14


# ---------------------------------------------------------------------------
# set_value：設定檔載入失敗 (L440-442)
# ---------------------------------------------------------------------------
class TestSetValueError:
    @patch("src.cli.config_tools.ConfigManager")
    def test_set_value_load_failure(self, mock_cm, tmp_path):
        """config 檔案損壞時 → 載入失敗訊息"""
        bad_path = tmp_path / "config.yaml"
        bad_path.write_text("not: valid", encoding="utf-8")
        mock_cm.return_value.config_path = bad_path
        # Make open raise an exception
        with patch("builtins.open", side_effect=PermissionError("denied")):
            from src.cli.config_tools import app as config_app
            result = runner.invoke(config_app, ["set", "llm.temperature", "0.7"])
            assert result.exit_code != 0
            assert "載入設定檔失敗" in result.output


# ---------------------------------------------------------------------------
# _mask_sensitive：list 分支 (L479)
# ---------------------------------------------------------------------------
class TestMaskSensitive:
    def test_mask_list_with_dicts(self):
        from src.cli.config_tools import _mask_sensitive
        data = [{"api_key": "secret123", "name": "test"}, "plain"]
        result = _mask_sensitive(data)
        assert result[0]["api_key"] == "***"
        assert result[0]["name"] == "test"
        assert result[1] == "plain"

    def test_mask_nested_list(self):
        from src.cli.config_tools import _mask_sensitive
        data = {"items": [{"password": "pwd", "x": 1}]}
        result = _mask_sensitive(data)
        assert result["items"][0]["password"] == "***"
        assert result["items"][0]["x"] == 1


# ---------------------------------------------------------------------------
# export：yaml 格式 (L500)
# ---------------------------------------------------------------------------
class TestExportYaml:
    @patch("src.cli.config_tools.ConfigManager")
    def test_export_yaml_format(self, mock_cm):
        mock_cm.return_value.config = {"llm": {"provider": "ollama"}}
        from src.cli.config_tools import app as config_app
        result = runner.invoke(config_app, ["export", "--format", "yaml"])
        assert result.exit_code == 0
        parsed = yaml.safe_load(result.output)
        assert parsed["llm"]["provider"] == "ollama"

    @patch("src.cli.config_tools.ConfigManager")
    def test_export_yaml_to_file(self, mock_cm, tmp_path):
        mock_cm.return_value.config = {"llm": {"provider": "gemini", "api_key": "sk-123"}}
        out = str(tmp_path / "out.yaml")
        from src.cli.config_tools import app as config_app
        result = runner.invoke(config_app, ["export", "--format", "yaml", "-o", out])
        assert result.exit_code == 0
        content = yaml.safe_load(Path(out).read_text(encoding="utf-8"))
        assert content["llm"]["api_key"] == "***"
