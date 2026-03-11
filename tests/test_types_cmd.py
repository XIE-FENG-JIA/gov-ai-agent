"""types_cmd.py 的單元測試。"""
from unittest.mock import patch

from src.cli.types_cmd import types_command, DOC_TYPE_INFO
from src.core.models import VALID_DOC_TYPES


class TestTypesCommand:
    """types 指令測試。"""

    def test_types_command_runs(self):
        """types_command 應能正常執行不拋例外。"""
        with patch("src.cli.types_cmd.console") as mock_console:
            types_command()
        assert mock_console.print.called

    def test_all_valid_types_have_info(self):
        """所有 VALID_DOC_TYPES 應在 DOC_TYPE_INFO 中有對應資訊。"""
        for dt in VALID_DOC_TYPES:
            assert dt in DOC_TYPE_INFO, f"缺少 DOC_TYPE_INFO 條目: {dt}"

    def test_doc_type_info_structure(self):
        """每個 DOC_TYPE_INFO 應包含 desc 和 example。"""
        for dt, info in DOC_TYPE_INFO.items():
            assert "desc" in info, f"{dt} 缺少 desc"
            assert "example" in info, f"{dt} 缺少 example"
            assert len(info["desc"]) > 0
            assert len(info["example"]) > 0

    def test_valid_doc_types_not_empty(self):
        """VALID_DOC_TYPES 應至少有 1 種類型。"""
        assert len(VALID_DOC_TYPES) >= 1
