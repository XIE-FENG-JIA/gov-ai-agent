"""formatter.py / memory.py graph node 邊界測試。"""
from unittest.mock import patch, MagicMock


class TestFormatDocument:
    """format_document node 測試。"""

    def test_missing_draft(self):
        from src.graph.nodes.formatter import format_document
        result = format_document({"requirement": {"doc_type": "函"}})
        assert result["phase"] == "failed"
        assert "草稿" in result["error"]

    def test_missing_requirement(self):
        from src.graph.nodes.formatter import format_document
        result = format_document({"draft": "主旨：測試"})
        assert result["phase"] == "failed"
        assert "需求" in result["error"]

    def test_exception_handling(self):
        from src.graph.nodes.formatter import format_document
        # requirement_dict 不是合法的 PublicDocRequirement → 觸發異常
        result = format_document({"draft": "主旨：測試", "requirement": {"bad": "data"}})
        assert result["phase"] == "failed"
        assert "失敗" in result["error"]

    def test_success_path(self):
        from src.graph.nodes.formatter import format_document
        with patch("src.agents.template.TemplateEngine") as MockTE:
            MockTE.return_value.parse_draft.return_value = {"主旨": "測試"}
            MockTE.return_value.apply_template.return_value = "格式化後的公文"
            result = format_document({
                "draft": "主旨：測試",
                "requirement": {
                    "doc_type": "函", "subject": "測試", "sender": "A",
                    "receiver": "B", "urgency": "普通件",
                },
            })
        assert result["phase"] == "document_formatted"
        assert result["formatted_draft"] == "格式化後的公文"


class TestFetchOrgMemory:
    """fetch_org_memory node 測試。"""

    def test_no_sender(self):
        from src.graph.nodes.memory import fetch_org_memory
        with patch("src.api.dependencies.get_org_memory", return_value=None):
            result = fetch_org_memory({"requirement": {}})
        assert result["phase"] == "memory_fetched"
        assert result["org_hints"] == ""

    def test_with_sender_and_memory(self):
        from src.graph.nodes.memory import fetch_org_memory
        mock_mem = MagicMock()
        mock_mem.get_writing_hints.return_value = "用語正式"
        with patch("src.api.dependencies.get_org_memory", return_value=mock_mem):
            result = fetch_org_memory({"requirement": {"sender": "台北市政府"}})
        assert result["org_hints"] == "用語正式"

    def test_exception_does_not_block(self):
        from src.graph.nodes.memory import fetch_org_memory
        with patch("src.api.dependencies.get_org_memory", side_effect=RuntimeError("DB down")):
            result = fetch_org_memory({"requirement": {"sender": "X"}})
        assert result["phase"] == "memory_fetched"
        assert result["org_hints"] == ""
