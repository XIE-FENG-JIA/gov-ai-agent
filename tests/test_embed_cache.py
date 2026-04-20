"""
KnowledgeBaseManager embedding 快取測試

不依賴 chromadb — 直接測試 _cached_embed 方法的快取行為。
"""
import importlib
import threading
import types
from unittest.mock import MagicMock, patch

import pytest

from src.core.llm import LLMProvider


@pytest.fixture
def mock_kb():
    """建立一個 KnowledgeBaseManager（chromadb 不可用時仍能建構）。"""
    llm = MagicMock(spec=LLMProvider)
    llm.embed.return_value = [0.1] * 384

    # 直接 import 並 mock chromadb 使其不可用，讓 KB 進入降級模式
    # 但 _cached_embed 仍然可用（它不依賴 chromadb）
    with patch.dict("sys.modules", {"chromadb": None}):
        from importlib import reload
        import src.knowledge.manager as mgr_module
        reload(mgr_module)
        kb = mgr_module.KnowledgeBaseManager("/fake/path", llm)

    # 確保 _cached_embed 可用
    assert hasattr(kb, "_cached_embed")
    return kb


class TestEmbedCache:
    """Embedding 快取核心邏輯測試"""

    def test_same_query_cached(self, mock_kb):
        """同一 query 第二次呼叫不應觸發 embed"""
        mock_kb._cached_embed("公文格式")
        mock_kb._cached_embed("公文格式")
        assert mock_kb.llm_provider.embed.call_count == 1

    def test_different_queries_not_cached(self, mock_kb):
        """不同 query 各自呼叫 embed"""
        mock_kb._cached_embed("公文格式")
        mock_kb._cached_embed("法規依據")
        assert mock_kb.llm_provider.embed.call_count == 2

    def test_empty_result_not_cached(self, mock_kb):
        """embed 回傳空列表時不寫入快取，下次重試"""
        mock_kb.llm_provider.embed.return_value = []
        result1 = mock_kb._cached_embed("空查詢")
        assert result1 == []
        assert len(mock_kb._embed_cache) == 0

        # 恢復後應重新 embed
        mock_kb.llm_provider.embed.return_value = [0.2] * 384
        result2 = mock_kb._cached_embed("空查詢")
        assert result2 == [0.2] * 384
        assert len(mock_kb._embed_cache) == 1

    def test_none_result_not_cached(self, mock_kb):
        """embed 回傳 None 時不寫入快取"""
        mock_kb.llm_provider.embed.return_value = None
        result = mock_kb._cached_embed("查詢")
        assert result is None
        assert len(mock_kb._embed_cache) == 0

    def test_cache_returns_correct_vector(self, mock_kb):
        """快取命中時返回正確的向量"""
        mock_kb.llm_provider.embed.return_value = [0.5] * 384
        v1 = mock_kb._cached_embed("測試")
        mock_kb.llm_provider.embed.return_value = [0.9] * 384  # 改變回傳值
        v2 = mock_kb._cached_embed("測試")  # 應返回快取的 [0.5]*384
        assert v1 == v2 == [0.5] * 384

    def test_thread_safety(self, mock_kb):
        """多執行緒並發存取不應崩潰"""
        errors = []

        def embed_query(i):
            try:
                mock_kb._cached_embed(f"查詢{i % 5}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=embed_query, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == [], f"執行緒安全錯誤: {errors}"
        # 只有 5 個不同的 query，最多 5 次 embed
        assert mock_kb.llm_provider.embed.call_count <= 5


def test_manager_import_survives_missing_temp_warning_helper():
    """warnings_compat 缺少 temporary helper 時，manager import 仍應可用。"""
    fake_warnings_compat = types.ModuleType("src.core.warnings_compat")
    fake_warnings_compat.suppress_known_third_party_deprecations = lambda: None

    with patch.dict(
        "sys.modules",
        {
            "chromadb": None,
            "src.core.warnings_compat": fake_warnings_compat,
        },
    ):
        import src.knowledge.manager as mgr_module

        mgr_module = importlib.reload(mgr_module)
        assert hasattr(mgr_module, "suppress_known_third_party_deprecations_temporarily")

        llm = MagicMock(spec=LLMProvider)
        llm.embed.return_value = [0.1] * 384
        kb = mgr_module.KnowledgeBaseManager("/fake/path", llm)

    assert kb._available is False
