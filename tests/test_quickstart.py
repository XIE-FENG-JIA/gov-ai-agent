"""quickstart.py 的單元測試。"""
from unittest.mock import patch, MagicMock

from src.cli.quickstart import quickstart, _print_llm_fix_hint


class TestQuickstart:
    """quickstart 指令測試。"""

    def test_no_config_file(self, tmp_path, monkeypatch):
        """缺少 config.yaml 時應提示建立。"""
        monkeypatch.chdir(tmp_path)
        with patch("src.cli.quickstart.console") as mock_console:
            quickstart()
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "config.yaml 不存在" in output or "缺少 config.yaml" in output

    def test_with_config_no_llm(self, tmp_path, monkeypatch):
        """config.yaml 存在但缺少 llm 區塊。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text("version: 1", encoding="utf-8")
        with patch("src.cli.quickstart.console") as mock_console:
            with patch("src.core.config.ConfigManager") as mock_cm:
                mock_cm.return_value.config = {}
                quickstart()
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "config.yaml 已存在" in output or "已就緒" in output

    def test_all_ok_shows_success(self, tmp_path, monkeypatch):
        """全部檢查通過時應顯示成功訊息。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text("llm:\n  provider: test", encoding="utf-8")

        mock_llm = MagicMock()
        mock_llm.check_connectivity.return_value = (True, None)

        mock_kb = MagicMock()
        mock_kb.get_stats.return_value = {"examples_count": 10}


        with patch("src.cli.quickstart.console"):
            with patch("src.core.config.ConfigManager") as mock_cm:
                mock_cm.return_value.config = {
                    "llm": {"provider": "test", "model": "m"},
                    "knowledge_base": {"path": str(tmp_path)},
                }
                with patch("src.core.llm.get_llm_factory") as mock_factory:
                    mock_factory.return_value = mock_llm
                    with patch("src.core.llm.LiteLLMProvider", spec=True):
                        with patch("src.knowledge.manager.KnowledgeBaseManager", return_value=mock_kb):
                            quickstart()


class TestPrintLlmFixHint:
    """_print_llm_fix_hint 測試。"""

    def test_ollama_hint(self):
        with patch("src.cli.quickstart.console") as mock_console:
            _print_llm_fix_hint("ollama")
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "ollama serve" in output

    def test_gemini_hint(self):
        with patch("src.cli.quickstart.console") as mock_console:
            _print_llm_fix_hint("gemini")
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "GEMINI_API_KEY" in output

    def test_openrouter_hint(self):
        with patch("src.cli.quickstart.console") as mock_console:
            _print_llm_fix_hint("openrouter")
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "LLM_API_KEY" in output

    def test_unknown_provider_hint(self):
        with patch("src.cli.quickstart.console") as mock_console:
            _print_llm_fix_hint("unknown_provider")
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "config.yaml" in output
