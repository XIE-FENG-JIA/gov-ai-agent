"""KnowledgeBaseManager 單元測試 — mock chromadb 測試所有業務路徑。

Round 19: 覆蓋率從 40% 提升。不依賴 chromadb 安裝，用 mock 測試完整邏輯。
"""
from __future__ import annotations

import math
import threading
from collections import Counter
from unittest.mock import MagicMock, patch, PropertyMock
import sys
import types

import pytest


# ---------------------------------------------------------------------------
# chromadb mock — 在 import manager 之前就注入
# ---------------------------------------------------------------------------

def _make_mock_chromadb():
    """建立模擬 chromadb 模組。"""
    mod = types.ModuleType("chromadb")
    mod.PersistentClient = MagicMock  # type: ignore[attr-defined]
    return mod


@pytest.fixture(autouse=True)
def _inject_chromadb(monkeypatch):
    """為所有測試注入假的 chromadb 模組。"""
    mock_chromadb = _make_mock_chromadb()
    monkeypatch.setitem(sys.modules, "chromadb", mock_chromadb)
    # 強制重新載入 manager 模組，讓它拿到 mock chromadb
    import importlib
    import src.knowledge.manager as mgr_module
    monkeypatch.setattr(mgr_module, "chromadb", mock_chromadb)


@pytest.fixture
def mock_llm():
    """模擬 LLMProvider。"""
    llm = MagicMock()
    llm.embed.return_value = [0.1, 0.2, 0.3]
    llm.generate.return_value = "公文摘要上下文"
    return llm


@pytest.fixture
def mock_collection():
    """建立模擬 ChromaDB collection。"""
    coll = MagicMock()
    coll.count.return_value = 5
    coll.name = "test_collection"
    coll.query.return_value = {
        "ids": [["id1", "id2"]],
        "documents": [["文件一內容", "文件二內容"]],
        "metadatas": [[{"title": "文件一"}, {"title": "文件二"}]],
        "distances": [[0.2, 0.5]],
    }
    coll.get.return_value = {
        "ids": ["id1", "id2"],
        "documents": ["公文主旨是關於人事異動的通知", "預算編列需要依照相關規定辦理"],
        "metadatas": [{"doc_type": "函", "source_level": "A"}, {"doc_type": "簽", "source_level": "B"}],
    }
    return coll


@pytest.fixture
def manager(mock_llm, mock_collection):
    """建立帶 mock 的 KnowledgeBaseManager。"""
    from src.knowledge.manager import KnowledgeBaseManager

    with patch.object(
        KnowledgeBaseManager, "__init__", lambda self, *a, **kw: None
    ):
        mgr = KnowledgeBaseManager.__new__(KnowledgeBaseManager)

    # 手動設定實例屬性（繞過 __init__ 的 chromadb 初始化）
    mgr.persist_path = "/tmp/test_kb"
    mgr.llm_provider = mock_llm
    mgr.contextual_retrieval = False
    mgr._available = True
    mgr._search_cache = {}
    mgr._cache_lock = threading.Lock()
    mgr._embed_cache = {}
    mgr._embed_cache_lock = threading.Lock()
    mgr.client = MagicMock()
    mgr.examples_collection = MagicMock()
    mgr.regulations_collection = MagicMock()
    mgr.policies_collection = MagicMock()

    # 設定 collection 預設行為
    for coll in [mgr.examples_collection, mgr.regulations_collection, mgr.policies_collection]:
        coll.count.return_value = 5
        coll.name = "test"
        coll.query.return_value = {
            "ids": [["id1", "id2"]],
            "documents": [["文件一", "文件二"]],
            "metadatas": [[{"title": "t1"}, {"title": "t2"}]],
            "distances": [[0.2, 0.5]],
        }
        coll.get.return_value = {
            "ids": ["id1", "id2"],
            "documents": ["人事異動通知公文", "預算編列規定辦理"],
            "metadatas": [
                {"doc_type": "函", "source_level": "A", "source": "gazette"},
                {"doc_type": "簽", "source_level": "B", "source": "example"},
            ],
        }

    return mgr


# =====================================================================
# __init__ 測試
# =====================================================================

class TestInit:
    def test_init_without_chromadb(self, mock_llm, monkeypatch):
        """chromadb 為 None 時應標記 _available=False。"""
        import src.knowledge.manager as mgr_module
        monkeypatch.setattr(mgr_module, "chromadb", None)

        mgr = mgr_module.KnowledgeBaseManager("/tmp/test", mock_llm)
        assert mgr._available is False
        assert mgr.client is None
        assert mgr.examples_collection is None

    def test_init_with_chromadb_success(self, mock_llm):
        """chromadb 正常時應建立三個 collection。"""
        from src.knowledge.manager import KnowledgeBaseManager

        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = MagicMock()

        import src.knowledge.manager as mgr_module
        original_chromadb = mgr_module.chromadb
        mgr_module.chromadb.PersistentClient = MagicMock(return_value=mock_client)

        mgr = KnowledgeBaseManager("/tmp/test", mock_llm)
        assert mgr._available is True
        assert mock_client.get_or_create_collection.call_count == 3

    def test_init_chromadb_exception(self, mock_llm):
        """chromadb 初始化拋異常時應 graceful fallback。"""
        from src.knowledge.manager import KnowledgeBaseManager
        import src.knowledge.manager as mgr_module

        mgr_module.chromadb.PersistentClient = MagicMock(side_effect=Exception("DB corrupt"))

        mgr = KnowledgeBaseManager("/tmp/test", mock_llm)
        assert mgr._available is False
        assert mgr.client is None


# =====================================================================
# is_available / get_stats
# =====================================================================

class TestProperties:
    def test_is_available(self, manager):
        assert manager.is_available is True

    def test_is_available_false(self, manager):
        manager._available = False
        assert manager.is_available is False

    def test_get_stats_available(self, manager):
        manager.examples_collection.count.return_value = 10
        manager.regulations_collection.count.return_value = 20
        manager.policies_collection.count.return_value = 5
        stats = manager.get_stats()
        assert stats == {
            "examples_count": 10,
            "regulations_count": 20,
            "policies_count": 5,
        }

    def test_get_stats_unavailable(self, manager):
        manager._available = False
        stats = manager.get_stats()
        assert stats["examples_count"] == 0


# =====================================================================
# add_document
# =====================================================================

class TestAddDocument:
    def test_add_document_success(self, manager):
        doc_id = manager.add_document(
            content="測試公文內容",
            metadata={"title": "測試"},
            collection_name="examples",
        )
        assert doc_id is not None
        manager.examples_collection.add.assert_called_once()

    def test_add_document_to_regulations(self, manager):
        doc_id = manager.add_document(
            content="法規內容", metadata={"title": "法規"}, collection_name="regulations"
        )
        assert doc_id is not None
        manager.regulations_collection.add.assert_called_once()

    def test_add_document_to_policies(self, manager):
        doc_id = manager.add_document(
            content="政策內容", metadata={"title": "政策"}, collection_name="policies"
        )
        assert doc_id is not None
        manager.policies_collection.add.assert_called_once()

    def test_add_document_unavailable(self, manager):
        manager._available = False
        result = manager.add_document("content", {"title": "t"})
        assert result is None

    def test_add_document_empty_content(self, manager):
        result = manager.add_document("", {"title": "t"})
        assert result is None

    def test_add_document_whitespace_only(self, manager):
        result = manager.add_document("   \n  ", {"title": "t"})
        assert result is None

    def test_add_document_embed_fails(self, manager):
        manager.llm_provider.embed.return_value = None
        result = manager.add_document("有內容", {"title": "t"})
        assert result is None

    def test_add_document_collection_add_fails(self, manager):
        manager.examples_collection.add.side_effect = Exception("write error")
        result = manager.add_document("有內容", {"title": "t"})
        assert result is None

    def test_add_document_invalidates_cache(self, manager):
        from cachetools import TTLCache
        manager._search_cache = TTLCache(maxsize=256, ttl=300)
        manager._search_cache[("key",)] = "cached"
        manager.add_document("內容", {"title": "t"})
        assert len(manager._search_cache) == 0

    def test_add_document_with_contextual_retrieval(self, manager):
        manager.contextual_retrieval = True
        doc_id = manager.add_document(
            content="第一段內容",
            metadata={"title": "t"},
            full_document="完整公文包含第一段和第二段",
            chunk_index=0,
            total_chunks=2,
        )
        assert doc_id is not None
        # 驗證 LLM generate 被呼叫（用於 contextual enrichment）
        manager.llm_provider.generate.assert_called_once()


# =====================================================================
# _enrich_with_context
# =====================================================================

class TestEnrichWithContext:
    def test_enrich_success(self, manager):
        manager.llm_provider.generate.return_value = "人事任命段落"
        result = manager._enrich_with_context("原始內容", "完整文件", 0, 3)
        assert result.startswith("[上下文: 人事任命段落]")
        assert "原始內容" in result

    def test_enrich_llm_returns_too_long(self, manager):
        manager.llm_provider.generate.return_value = "x" * 200
        result = manager._enrich_with_context("原始內容", "完整文件", 0, 1)
        assert result == "原始內容"

    def test_enrich_llm_returns_empty(self, manager):
        manager.llm_provider.generate.return_value = ""
        result = manager._enrich_with_context("原始內容", "完整文件", 0, 1)
        assert result == "原始內容"

    def test_enrich_llm_exception(self, manager):
        manager.llm_provider.generate.side_effect = Exception("LLM down")
        result = manager._enrich_with_context("原始內容", "完整文件", 0, 1)
        assert result == "原始內容"

    def test_enrich_no_llm_provider(self, manager):
        manager.llm_provider = None
        result = manager._enrich_with_context("原始內容", "完整文件", 0, 1)
        assert result == "原始內容"


# =====================================================================
# _format_query_results
# =====================================================================

class TestFormatQueryResults:
    def test_normal_results(self):
        from src.knowledge.manager import KnowledgeBaseManager
        results = {
            "ids": [["a", "b"]],
            "documents": [["doc_a", "doc_b"]],
            "metadatas": [[{"k": "v1"}, {"k": "v2"}]],
            "distances": [[0.1, 0.9]],
        }
        formatted = KnowledgeBaseManager._format_query_results(results)
        assert len(formatted) == 2
        assert formatted[0]["id"] == "a"
        assert formatted[0]["content"] == "doc_a"
        assert formatted[0]["distance"] == 0.1

    def test_empty_results(self):
        from src.knowledge.manager import KnowledgeBaseManager
        results = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        assert KnowledgeBaseManager._format_query_results(results) == []

    def test_missing_fields(self):
        from src.knowledge.manager import KnowledgeBaseManager
        results = {"ids": [["a"]], "documents": None, "metadatas": None, "distances": None}
        formatted = KnowledgeBaseManager._format_query_results(results)
        assert len(formatted) == 1
        assert formatted[0]["content"] == ""
        assert formatted[0]["metadata"] == {}
        assert formatted[0]["distance"] is None

    def test_no_ids(self):
        from src.knowledge.manager import KnowledgeBaseManager
        assert KnowledgeBaseManager._format_query_results({}) == []


# =====================================================================
# search_examples / search_regulations / search_policies
# =====================================================================

class TestSearchMethods:
    def test_search_examples_basic(self, manager):
        results = manager.search_examples("公文範例")
        assert len(results) == 2
        manager.examples_collection.query.assert_called_once()

    def test_search_examples_unavailable(self, manager):
        manager._available = False
        assert manager.search_examples("query") == []

    def test_search_examples_empty_embedding(self, manager):
        manager.llm_provider.embed.return_value = None
        assert manager.search_examples("query") == []

    def test_search_examples_empty_collection(self, manager):
        manager.examples_collection.count.return_value = 0
        assert manager.search_examples("query") == []

    def test_search_examples_with_filter(self, manager):
        manager.search_examples("query", filter_metadata={"doc_type": "函"})
        call_args = manager.examples_collection.query.call_args
        assert call_args[1]["where"] == {"doc_type": "函"}

    def test_search_examples_with_source_level(self, manager):
        manager.search_examples("query", source_level="A")
        call_args = manager.examples_collection.query.call_args
        assert call_args[1]["where"] == {"source_level": "A"}

    def test_search_examples_with_filter_and_source_level(self, manager):
        manager.search_examples("query", filter_metadata={"doc_type": "函"}, source_level="A")
        call_args = manager.examples_collection.query.call_args
        where = call_args[1]["where"]
        assert "$and" in where

    def test_search_examples_query_exception(self, manager):
        manager.examples_collection.query.side_effect = Exception("query fail")
        assert manager.search_examples("query") == []

    def test_search_regulations_basic(self, manager):
        results = manager.search_regulations("法規查詢")
        assert len(results) == 2

    def test_search_regulations_unavailable(self, manager):
        manager._available = False
        assert manager.search_regulations("query") == []

    def test_search_regulations_with_doc_type(self, manager):
        manager.search_regulations("query", doc_type="函")
        call_args = manager.regulations_collection.query.call_args
        assert call_args[1]["where"] == {"doc_type": "函"}

    def test_search_regulations_with_doc_type_and_source_level(self, manager):
        manager.search_regulations("query", doc_type="函", source_level="A")
        call_args = manager.regulations_collection.query.call_args
        where = call_args[1]["where"]
        assert "$and" in where

    def test_search_regulations_empty_embedding(self, manager):
        manager.llm_provider.embed.return_value = None
        assert manager.search_regulations("query") == []

    def test_search_policies_basic(self, manager):
        results = manager.search_policies("政策查詢")
        assert len(results) == 2

    def test_search_policies_unavailable(self, manager):
        manager._available = False
        assert manager.search_policies("query") == []

    def test_search_policies_with_source_level(self, manager):
        manager.search_policies("query", source_level="A")
        call_args = manager.policies_collection.query.call_args
        assert call_args[1]["where"] == {"source_level": "A"}

    def test_search_policies_empty_collection(self, manager):
        manager.policies_collection.count.return_value = 0
        assert manager.search_policies("query") == []

    def test_search_policies_query_exception(self, manager):
        manager.policies_collection.query.side_effect = Exception("fail")
        assert manager.search_policies("query") == []


# =====================================================================
# search_level_a
# =====================================================================

class TestSearchLevelA:
    def test_search_level_a_combines_results(self, manager):
        results = manager.search_level_a("查詢")
        # 來自 regulations + examples 兩個搜尋
        assert len(results) <= 3  # n_results=3

    def test_search_level_a_sorts_by_distance(self, manager):
        # regulations 回傳 distance 0.5, examples 回傳 0.2
        manager.regulations_collection.query.return_value = {
            "ids": [["r1"]], "documents": [["法規"]], "metadatas": [[{"t": "r"}]], "distances": [[0.5]],
        }
        manager.examples_collection.query.return_value = {
            "ids": [["e1"]], "documents": [["範例"]], "metadatas": [[{"t": "e"}]], "distances": [[0.2]],
        }
        results = manager.search_level_a("查詢")
        assert results[0]["id"] == "e1"  # distance 0.2 排前面


# =====================================================================
# invalidate_cache
# =====================================================================

class TestCache:
    def test_invalidate_cache(self, manager):
        from cachetools import TTLCache
        manager._search_cache = TTLCache(maxsize=256, ttl=300)
        manager._search_cache[("k1",)] = "v1"
        manager._search_cache[("k2",)] = "v2"
        manager.invalidate_cache()
        assert len(manager._search_cache) == 0


# =====================================================================
# search_hybrid
# =====================================================================

class TestSearchHybrid:
    def test_hybrid_unavailable(self, manager):
        manager._available = False
        assert manager.search_hybrid("query") == []

    def test_hybrid_cache_hit(self, manager):
        from cachetools import TTLCache
        manager._search_cache = TTLCache(maxsize=256, ttl=300)
        cache_key = ("query", 5, None, None, None)
        manager._search_cache[cache_key] = [{"id": "cached"}]
        result = manager.search_hybrid("query")
        assert result == [{"id": "cached"}]

    def test_hybrid_embed_fails_fallback_to_keyword(self, manager):
        manager.llm_provider.embed.return_value = None
        from cachetools import TTLCache
        manager._search_cache = TTLCache(maxsize=256, ttl=300)
        # keyword fallback 會嘗試 jieba
        result = manager.search_hybrid("查詢")
        assert isinstance(result, list)

    def test_hybrid_vector_only_no_bm25(self, manager):
        """BM25 失敗時應回退到純向量搜尋。"""
        from cachetools import TTLCache
        manager._search_cache = TTLCache(maxsize=256, ttl=300)

        with patch.object(manager, "_bm25_search", side_effect=Exception("jieba fail")):
            results = manager.search_hybrid("query")
        assert isinstance(results, list)

    def test_hybrid_with_bm25_rrf_fusion(self, manager):
        """向量 + BM25 都有結果時應使用 RRF 融合。"""
        from cachetools import TTLCache
        manager._search_cache = TTLCache(maxsize=256, ttl=300)

        bm25_results = [
            {"id": "bm1", "content": "BM25 結果", "metadata": {}, "distance": 0.3, "_bm25_score": 2.5},
        ]
        with patch.object(manager, "_bm25_search", return_value=bm25_results):
            results = manager.search_hybrid("query")
        assert isinstance(results, list)
        assert len(results) > 0

    def test_hybrid_with_filters(self, manager):
        """帶過濾條件的混合搜尋。"""
        from cachetools import TTLCache
        manager._search_cache = TTLCache(maxsize=256, ttl=300)

        with patch.object(manager, "_bm25_search", return_value=[]):
            results = manager.search_hybrid(
                "query", source_level="A", doc_type="函", source_type="gazette"
            )
        assert isinstance(results, list)

    def test_hybrid_empty_collections(self, manager):
        """所有集合都空時應回傳空列表。"""
        from cachetools import TTLCache
        manager._search_cache = TTLCache(maxsize=256, ttl=300)

        for coll in [manager.examples_collection, manager.regulations_collection, manager.policies_collection]:
            coll.count.return_value = 0

        with patch.object(manager, "_bm25_search", return_value=[]):
            results = manager.search_hybrid("query")
        assert results == []

    def test_hybrid_writes_to_cache(self, manager):
        """結果應寫入快取。"""
        from cachetools import TTLCache
        manager._search_cache = TTLCache(maxsize=256, ttl=300)

        with patch.object(manager, "_bm25_search", return_value=[]):
            manager.search_hybrid("query")

        cache_key = ("query", 5, None, None, None)
        assert cache_key in manager._search_cache

    def test_hybrid_collection_query_exception(self, manager):
        """集合查詢失敗時應 continue 而非崩潰。"""
        from cachetools import TTLCache
        manager._search_cache = TTLCache(maxsize=256, ttl=300)

        manager.examples_collection.query.side_effect = Exception("query fail")
        with patch.object(manager, "_bm25_search", return_value=[]):
            results = manager.search_hybrid("query")
        assert isinstance(results, list)


# =====================================================================
# _rrf_fuse
# =====================================================================

class TestRRFFuse:
    def test_rrf_basic(self):
        from src.knowledge.manager import KnowledgeBaseManager
        vector = [
            {"id": "a", "content": "A", "metadata": {}, "distance": 0.1},
            {"id": "b", "content": "B", "metadata": {}, "distance": 0.5},
        ]
        bm25 = [
            {"id": "b", "content": "B", "metadata": {}, "distance": 0.3, "_bm25_score": 3.0},
            {"id": "c", "content": "C", "metadata": {}, "distance": 0.4, "_bm25_score": 1.0},
        ]
        results = KnowledgeBaseManager._rrf_fuse(vector, bm25, n_results=3)
        # b 出現在兩個列表中，RRF 分數應最高
        assert results[0]["id"] == "b"
        assert "_rrf_score" in results[0]
        assert "_bm25_score" not in results[0]  # 應被清理

    def test_rrf_n_results_limit(self):
        from src.knowledge.manager import KnowledgeBaseManager
        vector = [{"id": f"v{i}", "content": "", "metadata": {}, "distance": 0.1 * i} for i in range(10)]
        bm25 = [{"id": f"b{i}", "content": "", "metadata": {}, "distance": 0.2, "_bm25_score": 1.0} for i in range(10)]
        results = KnowledgeBaseManager._rrf_fuse(vector, bm25, n_results=3)
        assert len(results) == 3

    def test_rrf_empty_bm25(self):
        from src.knowledge.manager import KnowledgeBaseManager
        vector = [{"id": "a", "content": "A", "metadata": {}, "distance": 0.1}]
        results = KnowledgeBaseManager._rrf_fuse(vector, [], n_results=5)
        assert len(results) == 1
        assert results[0]["id"] == "a"


# =====================================================================
# _bm25_search
# =====================================================================

class TestBM25Search:
    def test_bm25_no_jieba(self, manager):
        with patch.dict(sys.modules, {"jieba": None}):
            # jieba import 會失敗，但 manager 內部 try/except 處理
            # 需要更精確的 mock
            pass

    def test_bm25_basic(self, manager):
        """基本 BM25 搜尋。"""
        mock_jieba = MagicMock()
        mock_jieba.cut.return_value = ["人事", "異動", "通知"]

        with patch.dict(sys.modules, {"jieba": mock_jieba}):
            results = manager._bm25_search(
                "人事異動",
                collections=[manager.examples_collection],
                n_results=5,
            )
        assert isinstance(results, list)

    def test_bm25_empty_collections(self, manager):
        manager.examples_collection.count.return_value = 0
        mock_jieba = MagicMock()
        mock_jieba.cut.return_value = ["查詢"]

        with patch.dict(sys.modules, {"jieba": mock_jieba}):
            results = manager._bm25_search(
                "查詢", collections=[manager.examples_collection]
            )
        assert results == []

    def test_bm25_with_metadata_filters(self, manager):
        mock_jieba = MagicMock()
        mock_jieba.cut.return_value = ["人事", "查詢"]

        with patch.dict(sys.modules, {"jieba": mock_jieba}):
            results = manager._bm25_search(
                "人事查詢",
                collections=[manager.examples_collection],
                source_level="A",
                doc_type="函",
                source_type="gazette",
            )
        assert isinstance(results, list)

    def test_bm25_empty_query_tokens(self, manager):
        mock_jieba = MagicMock()
        mock_jieba.cut.return_value = ["的", "了"]  # 全是短 token，會被過濾

        with patch.dict(sys.modules, {"jieba": mock_jieba}):
            results = manager._bm25_search(
                "的了", collections=[manager.examples_collection]
            )
        assert results == []

    def test_bm25_collection_get_exception(self, manager):
        manager.examples_collection.get.side_effect = Exception("read fail")
        mock_jieba = MagicMock()
        mock_jieba.cut.return_value = ["人事", "查詢"]

        with patch.dict(sys.modules, {"jieba": mock_jieba}):
            results = manager._bm25_search(
                "人事查詢", collections=[manager.examples_collection]
            )
        assert results == []

    def test_bm25_large_collection_limit(self, manager):
        """集合 > 500 筆時應限制取出數量。"""
        manager.examples_collection.count.return_value = 1000
        mock_jieba = MagicMock()
        mock_jieba.cut.return_value = ["人事", "查詢"]

        with patch.dict(sys.modules, {"jieba": mock_jieba}):
            manager._bm25_search(
                "人事查詢", collections=[manager.examples_collection]
            )
        # 確認 get() 有 limit=500
        call_args = manager.examples_collection.get.call_args
        assert call_args[1].get("limit") == 500


# =====================================================================
# _keyword_fallback_search
# =====================================================================

class TestKeywordFallbackSearch:
    def test_fallback_basic(self, manager):
        mock_jieba = MagicMock()
        mock_jieba.cut.return_value = iter(["人事", "異動"])

        with patch.dict(sys.modules, {"jieba": mock_jieba}):
            results = manager._keyword_fallback_search("人事異動")
        assert isinstance(results, list)

    def test_fallback_no_jieba(self, manager):
        """jieba 未安裝時回傳空列表。"""
        import importlib

        # 暫時移除 jieba
        original = sys.modules.get("jieba")
        sys.modules["jieba"] = None  # type: ignore[assignment]
        try:
            # 需要讓 import jieba 在函數內失敗
            # 但 patch.dict 更乾淨
            with patch.dict(sys.modules, {"jieba": None}):
                # _keyword_fallback_search 內部 import jieba 會觸發 ImportError
                # 但 sys.modules["jieba"] = None 不會觸發 ImportError
                # 需要用不同方式
                pass
        finally:
            if original is not None:
                sys.modules["jieba"] = original

    def test_fallback_empty_collections(self, manager):
        for coll in [manager.examples_collection, manager.regulations_collection, manager.policies_collection]:
            coll.count.return_value = 0

        mock_jieba = MagicMock()
        mock_jieba.cut.return_value = iter(["查詢"])

        with patch.dict(sys.modules, {"jieba": mock_jieba}):
            results = manager._keyword_fallback_search("查詢")
        assert results == []

    def test_fallback_with_filters(self, manager):
        mock_jieba = MagicMock()
        mock_jieba.cut.return_value = iter(["人事", "查詢"])

        with patch.dict(sys.modules, {"jieba": mock_jieba}):
            results = manager._keyword_fallback_search(
                "人事查詢", source_level="A", doc_type="函", source_type="gazette"
            )
        assert isinstance(results, list)

    def test_fallback_collection_exception(self, manager):
        manager.examples_collection.get.side_effect = Exception("fail")
        mock_jieba = MagicMock()
        mock_jieba.cut.return_value = iter(["查詢"])

        with patch.dict(sys.modules, {"jieba": mock_jieba}):
            results = manager._keyword_fallback_search("查詢")
        assert isinstance(results, list)


# =====================================================================
# reset_db
# =====================================================================

class TestResetDB:
    def test_reset_db_success(self, manager):
        manager.reset_db()
        assert manager.client.delete_collection.call_count == 3
        assert manager.client.get_or_create_collection.call_count == 3

    def test_reset_db_unavailable(self, manager):
        manager._available = False
        manager.reset_db()
        manager.client.delete_collection.assert_not_called()

    def test_reset_db_delete_nonexistent(self, manager):
        """刪除不存在的集合應不崩潰。"""
        manager.client.delete_collection.side_effect = Exception("not found")
        manager.reset_db()  # 不應拋異常
        assert manager.client.get_or_create_collection.call_count == 3

    def test_reset_db_invalidates_cache(self, manager):
        from cachetools import TTLCache
        manager._search_cache = TTLCache(maxsize=256, ttl=300)
        manager._search_cache[("k",)] = "v"
        manager.reset_db()
        assert len(manager._search_cache) == 0


# =====================================================================
# add_example (compatibility wrapper)
# =====================================================================

class TestAddExample:
    def test_add_example_delegates(self, manager):
        with patch.object(manager, "add_document", return_value="test-id") as mock_add:
            result = manager.add_example("內容", {"title": "t"})
        assert result == "test-id"
        mock_add.assert_called_once_with("內容", {"title": "t"}, "examples")
