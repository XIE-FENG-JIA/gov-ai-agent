"""
src/knowledge/manager.py 的延伸測試
補充不同集合的操作、搜尋和邊界條件
"""
import pytest
from src.knowledge.manager import KnowledgeBaseManager


# ==================== Fixtures ====================

@pytest.fixture
def kb(tmp_path, mock_llm):
    """回傳一個使用臨時目錄的 KnowledgeBaseManager 實例。"""
    kb_dir = tmp_path / "kb_test"
    return KnowledgeBaseManager(str(kb_dir), mock_llm)


# ==================== add_document ====================

class TestAddDocument:
    """add_document 方法的測試"""

    def test_add_to_examples(self, kb):
        """測試新增到 examples 集合"""
        doc_id = kb.add_document("測試內容", {"title": "Test"}, "examples")
        assert doc_id is not None
        assert kb.get_stats()["examples_count"] == 1

    def test_add_to_regulations(self, kb):
        """測試新增到 regulations 集合"""
        doc_id = kb.add_document("法規內容", {"title": "法規"}, "regulations")
        assert doc_id is not None
        assert kb.get_stats()["regulations_count"] == 1

    def test_add_to_policies(self, kb):
        """測試新增到 policies 集合"""
        doc_id = kb.add_document("政策內容", {"title": "政策"}, "policies")
        assert doc_id is not None
        assert kb.get_stats()["policies_count"] == 1

    def test_add_default_collection(self, kb):
        """測試預設集合為 examples"""
        kb.add_document("內容", {"title": "預設"})
        assert kb.get_stats()["examples_count"] == 1

    def test_add_with_empty_embedding(self, kb, mock_llm):
        """測試 embedding 為空時回傳 None"""
        mock_llm.embed.return_value = []  # 空 embedding
        doc_id = kb.add_document("內容", {"title": "失敗"}, "examples")
        assert doc_id is None
        assert kb.get_stats()["examples_count"] == 0


# ==================== search_examples ====================

class TestSearchExamples:
    """search_examples 方法的測試"""

    def test_search_empty_collection(self, kb):
        """測試搜尋空集合回傳空列表"""
        results = kb.search_examples("查詢")
        assert results == []

    def test_search_with_results(self, kb):
        """測試搜尋有結果"""
        kb.add_document("資源回收公文範例", {"title": "回收函", "doc_type": "函"}, "examples")
        results = kb.search_examples("資源回收")
        assert len(results) == 1
        assert results[0]["metadata"]["title"] == "回收函"

    def test_search_with_empty_embedding(self, kb, mock_llm):
        """測試查詢 embedding 為空時回傳空列表"""
        kb.add_document("內容", {"title": "Test"}, "examples")
        mock_llm.embed.return_value = []
        results = kb.search_examples("查詢")
        assert results == []

    def test_search_n_results_limit(self, kb):
        """測試搜尋結果數量限制"""
        for i in range(5):
            kb.add_document(f"內容{i}", {"title": f"Doc{i}"}, "examples")
        results = kb.search_examples("查詢", n_results=2)
        assert len(results) <= 2

    def test_search_result_format(self, kb):
        """測試搜尋結果格式"""
        kb.add_document("測試內容", {"title": "格式測試"}, "examples")
        results = kb.search_examples("測試")
        assert len(results) == 1
        assert "id" in results[0]
        assert "content" in results[0]
        assert "metadata" in results[0]
        assert "distance" in results[0]


# ==================== search_regulations ====================

class TestSearchRegulations:
    """search_regulations 方法的測試"""

    def test_search_empty_regulations(self, kb):
        """測試搜尋空的法規集合"""
        results = kb.search_regulations("查詢")
        assert results == []

    def test_search_regulations_with_doc_type(self, kb):
        """測試帶 doc_type 過濾的法規搜尋"""
        kb.add_document("函的格式規則", {"title": "函規則", "doc_type": "函"}, "regulations")
        kb.add_document("公告的格式規則", {"title": "公告規則", "doc_type": "公告"}, "regulations")

        results = kb.search_regulations("格式", doc_type="函")
        assert len(results) >= 1
        assert all(r["metadata"]["doc_type"] == "函" for r in results)

    def test_search_regulations_without_filter(self, kb):
        """測試不帶過濾的法規搜尋"""
        kb.add_document("法規內容", {"title": "通用規則", "doc_type": "通用"}, "regulations")
        results = kb.search_regulations("法規")
        assert len(results) == 1

    def test_search_regulations_empty_embedding(self, kb, mock_llm):
        """測試查詢 embedding 為空時回傳空列表"""
        kb.add_document("法規", {"title": "Test"}, "regulations")
        mock_llm.embed.return_value = []
        results = kb.search_regulations("查詢")
        assert results == []


# ==================== search_policies ====================

class TestSearchPolicies:
    """search_policies 方法的測試"""

    def test_search_empty_policies(self, kb):
        """測試搜尋空的政策集合"""
        results = kb.search_policies("查詢")
        assert results == []

    def test_search_policies_with_results(self, kb):
        """測試政策搜尋有結果"""
        kb.add_document("淨零碳排政策內容", {"title": "淨零碳排"}, "policies")
        results = kb.search_policies("碳排放")
        assert len(results) == 1
        assert results[0]["metadata"]["title"] == "淨零碳排"

    def test_search_policies_empty_embedding(self, kb, mock_llm):
        """測試查詢 embedding 為空時回傳空列表"""
        kb.add_document("政策", {"title": "Test"}, "policies")
        mock_llm.embed.return_value = []
        results = kb.search_policies("查詢")
        assert results == []

    def test_search_policies_result_format(self, kb):
        """測試政策搜尋結果格式"""
        kb.add_document("政策內容", {"title": "格式測試"}, "policies")
        results = kb.search_policies("政策")
        assert len(results) == 1
        assert "content" in results[0]
        assert "metadata" in results[0]
        assert "distance" in results[0]


# ==================== get_stats ====================

class TestGetStats:
    """get_stats 方法的測試"""

    def test_empty_stats(self, kb):
        """測試空資料庫的統計"""
        stats = kb.get_stats()
        assert stats["examples_count"] == 0
        assert stats["regulations_count"] == 0
        assert stats["policies_count"] == 0

    def test_stats_after_adds(self, kb):
        """測試新增資料後的統計"""
        kb.add_document("e1", {"title": "E1"}, "examples")
        kb.add_document("e2", {"title": "E2"}, "examples")
        kb.add_document("r1", {"title": "R1"}, "regulations")
        kb.add_document("p1", {"title": "P1"}, "policies")
        kb.add_document("p2", {"title": "P2"}, "policies")

        stats = kb.get_stats()
        assert stats["examples_count"] == 2
        assert stats["regulations_count"] == 1
        assert stats["policies_count"] == 2


# ==================== reset_db ====================

class TestResetDB:
    """reset_db 方法的測試"""

    def test_reset_clears_all(self, kb):
        """測試重設資料庫清除所有資料"""
        kb.add_document("e1", {"title": "E1"}, "examples")
        kb.add_document("r1", {"title": "R1"}, "regulations")
        kb.add_document("p1", {"title": "P1"}, "policies")

        assert kb.get_stats()["examples_count"] > 0

        kb.reset_db()

        stats = kb.get_stats()
        assert stats["examples_count"] == 0
        assert stats["regulations_count"] == 0
        assert stats["policies_count"] == 0

    def test_reset_and_readd(self, kb):
        """測試重設後可重新新增"""
        kb.add_document("old", {"title": "Old"}, "examples")
        kb.reset_db()
        kb.add_document("new", {"title": "New"}, "examples")

        stats = kb.get_stats()
        assert stats["examples_count"] == 1


# ==================== add_example (legacy) ====================

class TestAddExample:
    """add_example 舊版相容方法的測試"""

    def test_add_example_adds_to_examples(self, kb):
        """測試 add_example 新增到 examples 集合"""
        doc_id = kb.add_example("內容", {"title": "Legacy"})
        assert doc_id is not None
        assert kb.get_stats()["examples_count"] == 1


# ==================== reset_db 邊界測試 ====================

class TestResetDBEdgeCases:
    """reset_db 方法的邊界測試"""

    def test_reset_when_unavailable(self, mock_llm):
        """測試知識庫不可用時 reset_db 安全返回"""
        kb = KnowledgeBaseManager.__new__(KnowledgeBaseManager)
        kb._available = False
        kb.llm = mock_llm
        # 不應拋出異常
        kb.reset_db()

    def test_reset_delete_collection_exception(self, kb):
        """測試刪除不存在的集合時優雅處理異常"""
        from unittest.mock import MagicMock
        original_client = kb.client
        mock_client = MagicMock(wraps=original_client)
        mock_client.delete_collection.side_effect = Exception("Collection not found")
        mock_client.get_or_create_collection = original_client.get_or_create_collection
        kb.client = mock_client
        # 不應拋出異常，且應重建集合
        kb.reset_db()
        assert mock_client.delete_collection.call_count == 3
        kb.client = original_client


# ==================== ChromaDB 操作異常處理 ====================

class TestChromaDBExceptionHandling:
    """ChromaDB 操作的例外處理測試"""

    def test_add_document_chromadb_write_failure(self, kb):
        """測試 add_document 寫入 ChromaDB 失敗時回傳 None"""
        from unittest.mock import MagicMock
        # Mock the collection's add method to raise
        original_collection = kb.examples_collection
        mock_collection = MagicMock()
        mock_collection.add.side_effect = Exception("Disk full")
        kb.examples_collection = mock_collection
        try:
            result = kb.add_document("測試內容", {"title": "Test"}, "examples")
            assert result is None
        finally:
            kb.examples_collection = original_collection

    def test_search_examples_query_failure(self, kb):
        """測試 search_examples 查詢 ChromaDB 失敗時回傳空列表"""
        from unittest.mock import MagicMock
        # 先加入一筆資料以確保 count > 0
        kb.add_document("測試", {"title": "Test"}, "examples")
        original_collection = kb.examples_collection
        mock_collection = MagicMock()
        mock_collection.count.side_effect = Exception("SQLite locked")
        kb.examples_collection = mock_collection
        try:
            results = kb.search_examples("測試查詢")
            assert results == []
        finally:
            kb.examples_collection = original_collection

    def test_search_regulations_query_failure(self, kb):
        """測試 search_regulations 查詢失敗時回傳空列表"""
        from unittest.mock import MagicMock
        mock_collection = MagicMock()
        mock_collection.count.return_value = 5
        mock_collection.query.side_effect = Exception("Index corrupted")
        original = kb.regulations_collection
        kb.regulations_collection = mock_collection
        try:
            results = kb.search_regulations("法規查詢")
            assert results == []
        finally:
            kb.regulations_collection = original

    def test_search_policies_query_failure(self, kb):
        """測試 search_policies 查詢失敗時回傳空列表"""
        from unittest.mock import MagicMock
        mock_collection = MagicMock()
        mock_collection.count.return_value = 3
        mock_collection.query.side_effect = Exception("Connection lost")
        original = kb.policies_collection
        kb.policies_collection = mock_collection
        try:
            results = kb.search_policies("政策查詢")
            assert results == []
        finally:
            kb.policies_collection = original


# ==================== BUG-004: 空字典 filter_metadata 防護 ====================

class TestEmptyFilterMetadata:
    """search_examples 傳入空字典 filter_metadata 應等同 None。"""

    def test_empty_dict_filter_returns_results(self, kb):
        """傳入 filter_metadata={} 不應靜默失敗，應返回結果"""
        kb.add_document("測試範例內容", {"title": "Test", "doc_type": "函"})
        # 空字典應等同 None（無過濾條件）
        results = kb.search_examples("測試", filter_metadata={})
        assert isinstance(results, list)
        # 應返回結果（因為有一筆文件）
        assert len(results) >= 1

    def test_none_filter_returns_results(self, kb):
        """傳入 filter_metadata=None 應正常返回結果"""
        kb.add_document("另一個測試", {"title": "Test2", "doc_type": "公告"})
        results = kb.search_examples("測試", filter_metadata=None)
        assert isinstance(results, list)
        assert len(results) >= 1


# ==================== BUG-013: n_results > count 防護 ====================

class TestNResultsClamp:
    """搜尋方法應將 n_results 限制在集合實際數量內。"""

    def test_search_examples_n_results_exceeds_count(self, kb):
        """n_results 超過集合數量時不應拋出異常"""
        kb.add_document("唯一文件", {"title": "Solo", "doc_type": "函"})
        # 集合只有 1 筆，要求 10 筆
        results = kb.search_examples("唯一", n_results=10)
        assert isinstance(results, list)
        assert len(results) == 1

    def test_search_policies_n_results_exceeds_count(self, kb):
        """policies 搜尋中 n_results 超過集合數量時不應拋出異常"""
        kb.add_document(
            "政策文件", {"title": "Policy1"}, collection_name="policies"
        )
        results = kb.search_policies("政策", n_results=10)
        assert isinstance(results, list)
        assert len(results) == 1

    def test_search_regulations_n_results_exceeds_count(self, kb):
        """regulations 搜尋中 n_results 超過集合數量時不應拋出異常"""
        kb.add_document(
            "法規文件", {"title": "Reg1", "doc_type": "函"},
            collection_name="regulations",
        )
        results = kb.search_regulations("法規", n_results=10)
        assert isinstance(results, list)
        assert len(results) == 1
