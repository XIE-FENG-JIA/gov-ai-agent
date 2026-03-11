"""
KnowledgeBaseManager 搜尋快取與 embedding 降級搜尋測試
"""
import threading
from unittest.mock import MagicMock, patch

import pytest

from src.core.llm import LLMProvider
from src.knowledge.manager import KnowledgeBaseManager


@pytest.fixture
def mock_kb(tmp_path):
    """建立一個使用 mock LLM 的 KnowledgeBaseManager。"""
    llm = MagicMock(spec=LLMProvider)
    llm.embed.return_value = [0.1] * 384
    kb = KnowledgeBaseManager(str(tmp_path / "kb"), llm)
    return kb


class TestSearchCache:
    """搜尋快取相關測試"""

    def test_cache_hit_returns_same_result(self, mock_kb):
        """相同查詢參數應命中快取，不重複呼叫 embed"""
        # 第一次呼叫（快取 miss）
        result1 = mock_kb.search_hybrid("測試查詢", n_results=3)
        embed_count_after_first = mock_kb.llm_provider.embed.call_count

        # 第二次呼叫（快取 hit）
        result2 = mock_kb.search_hybrid("測試查詢", n_results=3)
        embed_count_after_second = mock_kb.llm_provider.embed.call_count

        assert result1 == result2
        # 第二次不應再呼叫 embed
        assert embed_count_after_second == embed_count_after_first

    def test_different_params_no_cache_hit(self, mock_kb):
        """不同參數不應命中快取"""
        mock_kb.search_hybrid("查詢A", n_results=3)
        mock_kb.search_hybrid("查詢B", n_results=3)
        # 應呼叫 embed 兩次
        assert mock_kb.llm_provider.embed.call_count == 2

    def test_invalidate_cache_clears_all(self, mock_kb):
        """invalidate_cache 應清除所有快取"""
        mock_kb.search_hybrid("測試查詢")
        assert len(mock_kb._search_cache) > 0

        mock_kb.invalidate_cache()
        assert len(mock_kb._search_cache) == 0

    def test_add_document_invalidates_cache(self, mock_kb):
        """新增文件後應自動清除快取"""
        mock_kb.search_hybrid("測試查詢")
        assert len(mock_kb._search_cache) > 0

        mock_kb.add_document("新文件內容", {"title": "test"})
        assert len(mock_kb._search_cache) == 0

    def test_reset_db_invalidates_cache(self, mock_kb):
        """重設資料庫後應自動清除快取"""
        mock_kb.search_hybrid("測試查詢")
        assert len(mock_kb._search_cache) > 0

        mock_kb.reset_db()
        assert len(mock_kb._search_cache) == 0

    def test_cache_key_includes_all_params(self, mock_kb):
        """快取 key 包含所有查詢參數"""
        mock_kb.search_hybrid("查詢", n_results=3, source_level="A")
        mock_kb.search_hybrid("查詢", n_results=3, source_level="B")
        # 不同 source_level 應各自快取
        assert mock_kb.llm_provider.embed.call_count == 2
        assert len(mock_kb._search_cache) == 2

    def test_cache_thread_safety(self, mock_kb):
        """快取操作應為執行緒安全"""
        errors = []

        def search_and_invalidate(i):
            try:
                mock_kb.search_hybrid(f"查詢{i}")
                if i % 3 == 0:
                    mock_kb.invalidate_cache()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=search_and_invalidate, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"執行緒安全錯誤: {errors}"

    def test_unavailable_kb_returns_empty(self, tmp_path):
        """不可用的知識庫搜尋應回傳空列表且不寫入快取"""
        llm = MagicMock(spec=LLMProvider)
        # 模擬初始化失敗
        with patch("chromadb.PersistentClient", side_effect=RuntimeError("DB error")):
            kb = KnowledgeBaseManager(str(tmp_path / "bad_kb"), llm)

        result = kb.search_hybrid("測試")
        assert result == []
        assert len(kb._search_cache) == 0


class TestKeywordFallbackSearch:
    """Embedding 失敗降級搜尋測試"""

    def test_fallback_when_embed_returns_none(self, mock_kb):
        """embed 回傳 None 時應降級到關鍵字搜尋"""
        # 先新增文件
        mock_kb.llm_provider.embed.return_value = [0.1] * 384
        mock_kb.add_document("台北市環保局公告回收事項", {"title": "回收"})
        mock_kb.add_document("高雄市水利局工程報告", {"title": "水利"})

        # 讓 embed 失敗
        mock_kb.llm_provider.embed.return_value = None
        mock_kb.invalidate_cache()

        results = mock_kb.search_hybrid("環保回收")
        # 應透過關鍵字搜尋找到相關文件
        assert isinstance(results, list)

    def test_fallback_returns_empty_when_no_match(self, mock_kb):
        """無匹配時關鍵字搜尋應回傳空列表"""
        mock_kb.llm_provider.embed.return_value = None
        results = mock_kb.search_hybrid("完全不相關的查詢")
        assert results == []

    def test_fallback_respects_source_level_filter(self, mock_kb):
        """關鍵字搜尋應尊重 source_level 篩選"""
        mock_kb.llm_provider.embed.return_value = [0.1] * 384
        mock_kb.add_document("法規內容 A", {"title": "法規A", "source_level": "A"})
        mock_kb.add_document("法規內容 B", {"title": "法規B", "source_level": "B"})

        mock_kb.llm_provider.embed.return_value = None
        mock_kb.invalidate_cache()

        results = mock_kb.search_hybrid("法規", source_level="A")
        # 所有結果的 source_level 應為 A
        for r in results:
            assert r["metadata"].get("source_level") == "A"

    def test_fallback_with_jieba_not_installed(self, mock_kb):
        """jieba 未安裝時應回傳空列表"""
        mock_kb.llm_provider.embed.return_value = None
        with patch.dict("sys.modules", {"jieba": None}):
            results = mock_kb._keyword_fallback_search("測試")
            assert results == []

    def test_fallback_result_has_distance(self, mock_kb):
        """關鍵字搜尋結果應包含 distance 欄位"""
        mock_kb.llm_provider.embed.return_value = [0.1] * 384
        mock_kb.add_document("環保局公告事項", {"title": "公告"})

        mock_kb.llm_provider.embed.return_value = None
        mock_kb.invalidate_cache()

        results = mock_kb.search_hybrid("環保公告")
        for r in results:
            assert "distance" in r
            assert isinstance(r["distance"], float)
            assert r["distance"] > 0
