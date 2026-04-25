"""stats_cmd.py 的單元測試。"""
import json
from unittest.mock import patch

from src.cli.stats_cmd import stats
from src.cli.utils import set_state_dir


class TestStatsCommand:
    """stats 指令測試。"""

    def test_no_history_file(self, tmp_path, monkeypatch):
        """無歷史記錄檔案時應正常輸出。"""
        set_state_dir(None)
        monkeypatch.chdir(tmp_path)
        with patch("src.cli.stats_cmd.console") as mock_console:
            stats()
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "尚無記錄" in output

    def test_with_history(self, tmp_path, monkeypatch):
        """有歷史記錄時應顯示統計。"""
        monkeypatch.chdir(tmp_path)
        history = [
            {"status": "success", "doc_type": "函", "score": 0.9},
            {"status": "success", "doc_type": "函", "score": 0.8},
            {"status": "failed", "doc_type": "公告"},
        ]
        (tmp_path / ".gov-ai-history.json").write_text(
            json.dumps(history, ensure_ascii=False), encoding="utf-8",
        )
        with patch("src.cli.stats_cmd.console") as mock_console:
            with patch("src.core.config.ConfigManager") as mock_cm:
                mock_cm.return_value.config = {"llm": {"provider": "test", "model": "m"}}
                stats()
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "3" in output  # 總計 3 筆

    def test_corrupted_history(self, tmp_path, monkeypatch):
        """歷史記錄損壞時 JSONStore 優雅降級為空列表，stats 顯示 0 筆。"""
        set_state_dir(None)
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gov-ai-history.json").write_text("not json", encoding="utf-8")
        with patch("src.cli.stats_cmd.console") as mock_console:
            stats()
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        # JSONStore 遇到損壞 JSON 會回傳預設值 []，stats 將其視為 0 筆記錄
        assert "0 筆" in output

    def test_kb_dir_exists(self, tmp_path, monkeypatch):
        """知識庫目錄存在時顯示檔案數。"""
        monkeypatch.chdir(tmp_path)
        kb_dir = tmp_path / "kb_data"
        kb_dir.mkdir()
        (kb_dir / "file1.md").write_text("test", encoding="utf-8")
        (kb_dir / "file2.md").write_text("test", encoding="utf-8")

        with patch("src.cli.stats_cmd.console") as mock_console:
            with patch("src.core.config.ConfigManager") as mock_cm:
                mock_cm.return_value.config = {
                    "knowledge_base": {"path": str(kb_dir)},
                    "llm": {"provider": "test", "model": "m"},
                }
                stats()
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "2" in output  # 2 個檔案
