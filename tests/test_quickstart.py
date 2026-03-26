"""quickstart.py + doctor.py 的單元測試。"""
from unittest.mock import patch, MagicMock

from src.cli.quickstart import quickstart, _print_llm_fix_hint
from src.cli.doctor import doctor
from src.core.llm import LiteLLMProvider


# ── helpers ───────────────────────────────────────────

def _collect_output(mock_console) -> str:
    """從 mock console 蒐集所有 print 輸出為單一字串。"""
    return " ".join(str(c) for c in mock_console.print.call_args_list)


def _make_litellm_mock(**kwargs):
    """建立一個通過 isinstance(x, LiteLLMProvider) 檢查的 mock。"""
    mock = MagicMock(spec=LiteLLMProvider)
    for k, v in kwargs.items():
        setattr(mock, k, v)
    return mock


# ============================================================
# quickstart.py
# ============================================================


class TestQuickstart:
    """quickstart 指令測試。"""

    def test_no_config_file(self, tmp_path, monkeypatch):
        """缺少 config.yaml 時應提示建立。"""
        monkeypatch.chdir(tmp_path)
        with patch("src.cli.quickstart.console") as mock_console:
            quickstart()
        output = _collect_output(mock_console)
        assert "config.yaml 不存在" in output or "缺少 config.yaml" in output

    def test_with_config_no_llm(self, tmp_path, monkeypatch):
        """config.yaml 存在但缺少 llm 區塊。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text("version: 1", encoding="utf-8")
        with patch("src.cli.quickstart.console") as mock_console:
            with patch("src.core.config.ConfigManager") as mock_cm:
                mock_cm.return_value.config = {}
                quickstart()
        output = _collect_output(mock_console)
        assert "config.yaml 已存在" in output or "已就緒" in output

    def test_all_ok_shows_success(self, tmp_path, monkeypatch):
        """全部檢查通過時應顯示成功訊息。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text("llm:\n  provider: test", encoding="utf-8")

        mock_llm = _make_litellm_mock()
        mock_llm.check_connectivity.return_value = (True, None)

        mock_kb = MagicMock()
        mock_kb.get_stats.return_value = {"examples_count": 10}

        with patch("src.cli.quickstart.console") as mock_console:
            with patch("src.core.config.ConfigManager") as mock_cm:
                mock_cm.return_value.config = {
                    "llm": {"provider": "test", "model": "m"},
                    "knowledge_base": {"path": str(tmp_path)},
                }
                with patch("src.core.llm.get_llm_factory", return_value=mock_llm):
                    with patch("src.knowledge.manager.KnowledgeBaseManager", return_value=mock_kb):
                        quickstart()
        # quickstart 全部通過應完成不崩潰，且有多次 print（含 Panel + Table）
        assert mock_console.print.call_count >= 5

    def test_llm_connectivity_fail(self, tmp_path, monkeypatch):
        """LLM 連線失敗時應顯示錯誤與修復提示。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text("llm:\n  provider: ollama", encoding="utf-8")

        mock_llm = _make_litellm_mock()
        mock_llm.check_connectivity.return_value = (False, "Connection refused")

        with patch("src.cli.quickstart.console") as mock_console:
            with patch("src.core.config.ConfigManager") as mock_cm:
                mock_cm.return_value.config = {
                    "llm": {"provider": "ollama", "model": "m"},
                    "knowledge_base": {"path": str(tmp_path)},
                }
                with patch("src.core.llm.get_llm_factory", return_value=mock_llm):
                    quickstart()
        output = _collect_output(mock_console)
        assert "連線失敗" in output
        assert "ollama serve" in output

    def test_llm_non_litellm_provider(self, tmp_path, monkeypatch):
        """非 LiteLLMProvider 的 LLM 應直接標記為已設定。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text("llm:\n  provider: mock", encoding="utf-8")

        # 普通 MagicMock 不會通過 isinstance(llm, LiteLLMProvider)
        mock_llm = MagicMock()

        with patch("src.cli.quickstart.console") as mock_console:
            with patch("src.core.config.ConfigManager") as mock_cm:
                mock_cm.return_value.config = {
                    "llm": {"provider": "mock"},
                    "knowledge_base": {"path": str(tmp_path)},
                }
                with patch("src.core.llm.get_llm_factory", return_value=mock_llm):
                    with patch("src.knowledge.manager.KnowledgeBaseManager") as mock_kb_cls:
                        mock_kb_cls.return_value.get_stats.return_value = {"examples_count": 0}
                        quickstart()
        output = _collect_output(mock_console)
        assert "已設定" in output

    def test_llm_init_exception(self, tmp_path, monkeypatch):
        """LLM 初始化失敗時應顯示例外訊息。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text("llm:\n  provider: bad", encoding="utf-8")

        with patch("src.cli.quickstart.console") as mock_console:
            with patch("src.core.config.ConfigManager") as mock_cm:
                mock_cm.return_value.config = {"llm": {"provider": "bad"}}
                with patch("src.core.llm.get_llm_factory", side_effect=ValueError("bad config")):
                    quickstart()
        output = _collect_output(mock_console)
        assert "初始化失敗" in output

    def test_kb_no_examples(self, tmp_path, monkeypatch):
        """知識庫無範例時應顯示提示。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text("llm:\n  provider: test", encoding="utf-8")

        mock_llm = _make_litellm_mock()
        mock_llm.check_connectivity.return_value = (True, None)
        mock_kb = MagicMock()
        mock_kb.get_stats.return_value = {"examples_count": 0}

        with patch("src.cli.quickstart.console") as mock_console:
            with patch("src.core.config.ConfigManager") as mock_cm:
                mock_cm.return_value.config = {
                    "llm": {"provider": "test"},
                    "knowledge_base": {"path": str(tmp_path)},
                }
                with patch("src.core.llm.get_llm_factory", return_value=mock_llm):
                    with patch("src.knowledge.manager.KnowledgeBaseManager", return_value=mock_kb):
                        quickstart()
        output = _collect_output(mock_console)
        assert "未匯入範例" in output or "kb ingest" in output

    def test_kb_exception(self, tmp_path, monkeypatch):
        """知識庫初始化失敗時應顯示錯誤但不崩潰。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text("llm:\n  provider: test", encoding="utf-8")

        mock_llm = _make_litellm_mock()
        mock_llm.check_connectivity.return_value = (True, None)

        with patch("src.cli.quickstart.console") as mock_console:
            with patch("src.core.config.ConfigManager") as mock_cm:
                mock_cm.return_value.config = {
                    "llm": {"provider": "test"},
                    "knowledge_base": {"path": str(tmp_path)},
                }
                with patch("src.core.llm.get_llm_factory", return_value=mock_llm):
                    with patch("src.knowledge.manager.KnowledgeBaseManager", side_effect=RuntimeError("chroma error")):
                        quickstart()
        output = _collect_output(mock_console)
        assert "檢查失敗" in output


class TestPrintLlmFixHint:
    """_print_llm_fix_hint 測試。"""

    def test_ollama_hint(self):
        with patch("src.cli.quickstart.console") as mock_console:
            _print_llm_fix_hint("ollama")
        output = _collect_output(mock_console)
        assert "ollama serve" in output

    def test_gemini_hint(self):
        with patch("src.cli.quickstart.console") as mock_console:
            _print_llm_fix_hint("gemini")
        output = _collect_output(mock_console)
        assert "GEMINI_API_KEY" in output

    def test_openrouter_hint(self):
        with patch("src.cli.quickstart.console") as mock_console:
            _print_llm_fix_hint("openrouter")
        output = _collect_output(mock_console)
        assert "LLM_API_KEY" in output

    def test_unknown_provider_hint(self):
        with patch("src.cli.quickstart.console") as mock_console:
            _print_llm_fix_hint("unknown_provider")
        output = _collect_output(mock_console)
        assert "config.yaml" in output


# ============================================================
# doctor.py
# ============================================================


class TestDoctor:
    """doctor 指令覆蓋率補充測試。"""

    def test_doctor_all_ok(self, tmp_path, monkeypatch):
        """所有項目通過時應顯示「系統就緒」。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text("version: 1", encoding="utf-8")
        (tmp_path / "kb").mkdir()

        with patch("src.cli.doctor.console") as mock_console:
            with patch("src.core.config.ConfigManager") as mock_cm:
                mock_cm.return_value.config = {
                    "llm": {"provider": "test", "model": "m"},
                    "knowledge_base": {"path": str(tmp_path / "kb")},
                }
                doctor()
        output = _collect_output(mock_console)
        assert "系統就緒" in output

    def test_doctor_no_config(self, tmp_path, monkeypatch):
        """缺少 config.yaml 時應標記 ✗ 並顯示修復提示。"""
        monkeypatch.chdir(tmp_path)
        # 不建立 config.yaml

        with patch("src.cli.doctor.console") as mock_console:
            with patch("src.core.config.ConfigManager", side_effect=OSError("No config")):
                doctor()
        output = _collect_output(mock_console)
        assert "需要修復" in output or "config init" in output

    def test_doctor_kb_dir_missing(self, tmp_path, monkeypatch):
        """知識庫目錄不存在時應走 △ 分支（不崩潰）。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text("version: 1", encoding="utf-8")

        with patch("src.cli.doctor.console") as mock_console:
            with patch("src.core.config.ConfigManager") as mock_cm:
                mock_cm.return_value.config = {
                    "llm": {"provider": "test", "model": "m"},
                    "knowledge_base": {"path": str(tmp_path / "nonexistent_kb")},
                }
                doctor()
        # △ 不是 ✗，所以仍會顯示「系統就緒」
        output = _collect_output(mock_console)
        assert "系統就緒" in output
        assert mock_console.print.call_count >= 2

    def test_doctor_config_exception(self, tmp_path, monkeypatch):
        """ConfigManager 拋出例外時應優雅降級（不崩潰）。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text("version: 1", encoding="utf-8")

        with patch("src.cli.doctor.console") as mock_console:
            with patch("src.core.config.ConfigManager", side_effect=ValueError("bad yaml")):
                doctor()
        # 應有「需要修復」提示（因為 config 讀取失敗觸發 ✗）
        output = _collect_output(mock_console)
        assert "需要修復" in output or mock_console.print.call_count >= 2

    def test_doctor_missing_packages(self, tmp_path, monkeypatch):
        """必要套件缺少時應走 ✗ 分支。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text("version: 1", encoding="utf-8")

        original_import = __import__

        def mock_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError("No module named 'yaml'")
            return original_import(name, *args, **kwargs)

        with patch("src.cli.doctor.console") as mock_console:
            with patch("src.core.config.ConfigManager") as mock_cm:
                mock_cm.return_value.config = {
                    "llm": {"provider": "test", "model": "m"},
                    "knowledge_base": {"path": str(tmp_path)},
                }
                with patch("builtins.__import__", side_effect=mock_import):
                    doctor()
        # 至少有 Table + 結尾訊息
        assert mock_console.print.call_count >= 2

    def test_doctor_python_version_display(self, tmp_path, monkeypatch):
        """doctor 完整執行不崩潰。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text("version: 1", encoding="utf-8")

        with patch("src.cli.doctor.console") as mock_console:
            with patch("src.core.config.ConfigManager") as mock_cm:
                mock_cm.return_value.config = {
                    "llm": {"provider": "p", "model": "m"},
                    "knowledge_base": {"path": str(tmp_path)},
                }
                doctor()
        assert mock_console.print.call_count >= 2
