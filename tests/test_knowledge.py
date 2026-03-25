import pytest
from unittest.mock import MagicMock, patch

chromadb = pytest.importorskip("chromadb", reason="chromadb 未安裝，跳過知識庫測試")

from src.knowledge.manager import KnowledgeBaseManager


def test_kb_add_and_search(tmp_path, mock_llm):
    """Test adding and searching documents in KB."""
    kb_dir = tmp_path / "kb_test"
    kb = KnowledgeBaseManager(str(kb_dir), mock_llm)

    # Test Stats (Empty)
    stats = kb.get_stats()
    assert stats["examples_count"] == 0

    # Test Add
    metadata = {"title": "Test Doc", "doc_type": "函"}
    doc_id = kb.add_example("This is a test content.", metadata)
    assert doc_id is not None
    assert kb.get_stats()["examples_count"] == 1

    # Test Search (Mocking the embedding query)
    # ChromaDB's query will run against the mock embedding [0.1, 0.1...]
    # Since we only have 1 doc, it should return it.
    results = kb.search_examples("query")
    assert len(results) == 1
    assert results[0]["metadata"]["title"] == "Test Doc"


# ============================================================
# KR4: Hybrid Search 單元測試
# ============================================================


class TestRRFFuse:
    """_rrf_fuse 靜態方法的單元測試"""

    def test_basic_fusion_two_rankings(self):
        """給兩個排名清單，驗證 RRF 融合結果包含兩者的文件"""
        vector_results = [
            {"id": "a", "content": "文件A", "metadata": {}, "distance": 0.1},
            {"id": "b", "content": "文件B", "metadata": {}, "distance": 0.3},
            {"id": "c", "content": "文件C", "metadata": {}, "distance": 0.5},
        ]
        bm25_results = [
            {"id": "b", "content": "文件B", "metadata": {}, "distance": 0.2, "_bm25_score": 3.0},
            {"id": "d", "content": "文件D", "metadata": {}, "distance": 0.4, "_bm25_score": 2.0},
            {"id": "a", "content": "文件A", "metadata": {}, "distance": 0.6, "_bm25_score": 1.0},
        ]
        result = KnowledgeBaseManager._rrf_fuse(vector_results, bm25_results, n_results=3)

        assert len(result) == 3
        result_ids = [r["id"] for r in result]
        # a 和 b 在兩個清單中都有出現，RRF 分數較高，應排在前面
        assert "a" in result_ids
        assert "b" in result_ids

    def test_rrf_score_is_populated(self):
        """驗證融合結果包含 _rrf_score 欄位"""
        vector_results = [
            {"id": "x", "content": "X", "metadata": {}, "distance": 0.1},
        ]
        bm25_results = [
            {"id": "x", "content": "X", "metadata": {}, "distance": 0.1, "_bm25_score": 5.0},
        ]
        result = KnowledgeBaseManager._rrf_fuse(vector_results, bm25_results, n_results=5)

        assert len(result) == 1
        assert "_rrf_score" in result[0]
        assert result[0]["_rrf_score"] > 0

    def test_bm25_score_cleaned_from_output(self):
        """驗證融合結果已清除 _bm25_score 內部欄位"""
        vector_results = [
            {"id": "v1", "content": "V1", "metadata": {}, "distance": 0.2},
        ]
        bm25_results = [
            {"id": "b1", "content": "B1", "metadata": {}, "distance": 0.3, "_bm25_score": 2.5},
        ]
        result = KnowledgeBaseManager._rrf_fuse(vector_results, bm25_results, n_results=5)

        for doc in result:
            assert "_bm25_score" not in doc

    def test_n_results_limit(self):
        """驗證 n_results 確實限制了回傳數量"""
        vector_results = [
            {"id": f"v{i}", "content": f"V{i}", "metadata": {}, "distance": i * 0.1}
            for i in range(10)
        ]
        bm25_results = [
            {"id": f"b{i}", "content": f"B{i}", "metadata": {}, "distance": i * 0.1, "_bm25_score": 10 - i}
            for i in range(10)
        ]
        result = KnowledgeBaseManager._rrf_fuse(vector_results, bm25_results, n_results=3)
        assert len(result) == 3

    def test_empty_vector_results(self):
        """向量搜尋為空時，結果全來自 BM25"""
        bm25_results = [
            {"id": "b1", "content": "B1", "metadata": {}, "distance": 0.2, "_bm25_score": 3.0},
            {"id": "b2", "content": "B2", "metadata": {}, "distance": 0.4, "_bm25_score": 1.0},
        ]
        result = KnowledgeBaseManager._rrf_fuse([], bm25_results, n_results=5)
        assert len(result) == 2
        assert result[0]["id"] == "b1"

    def test_empty_bm25_results(self):
        """BM25 為空時，結果全來自向量搜尋"""
        vector_results = [
            {"id": "v1", "content": "V1", "metadata": {}, "distance": 0.1},
            {"id": "v2", "content": "V2", "metadata": {}, "distance": 0.3},
        ]
        result = KnowledgeBaseManager._rrf_fuse(vector_results, [], n_results=5)
        assert len(result) == 2
        assert result[0]["id"] == "v1"

    def test_both_empty(self):
        """兩個清單都空時回傳空清單"""
        result = KnowledgeBaseManager._rrf_fuse([], [], n_results=5)
        assert result == []

    def test_duplicate_doc_in_both_gets_higher_score(self):
        """同一文件同時出現在兩個排名中，RRF 分數應高於只出現在一個排名的文件"""
        vector_results = [
            {"id": "shared", "content": "Shared", "metadata": {}, "distance": 0.1},
            {"id": "only_vec", "content": "OnlyVec", "metadata": {}, "distance": 0.2},
        ]
        bm25_results = [
            {"id": "shared", "content": "Shared", "metadata": {}, "distance": 0.1, "_bm25_score": 5.0},
            {"id": "only_bm25", "content": "OnlyBM25", "metadata": {}, "distance": 0.3, "_bm25_score": 4.0},
        ]
        result = KnowledgeBaseManager._rrf_fuse(vector_results, bm25_results, n_results=5)

        # shared 在兩個排名中都排第一，RRF 分數最高
        assert result[0]["id"] == "shared"
        shared_score = result[0]["_rrf_score"]
        for doc in result[1:]:
            assert doc["_rrf_score"] < shared_score

    def test_custom_k_value(self):
        """自訂 k 值應改變 RRF 分數"""
        vector_results = [
            {"id": "a", "content": "A", "metadata": {}, "distance": 0.1},
        ]
        bm25_results = [
            {"id": "a", "content": "A", "metadata": {}, "distance": 0.1, "_bm25_score": 1.0},
        ]
        result_k60 = KnowledgeBaseManager._rrf_fuse(vector_results, bm25_results, n_results=1, k=60)
        result_k10 = KnowledgeBaseManager._rrf_fuse(vector_results, bm25_results, n_results=1, k=10)

        # k 值較小 → 排名影響更大 → RRF 分數較高
        assert result_k10[0]["_rrf_score"] > result_k60[0]["_rrf_score"]


class TestBM25Search:
    """_bm25_search 方法的單元測試（使用 mock chromadb collection）"""

    def _make_mock_collection(self, docs: list[dict], name: str = "test_coll") -> MagicMock:
        """建立一個 mock chromadb collection，包含指定的文件"""
        coll = MagicMock()
        coll.name = name
        coll.count.return_value = len(docs)

        # 模擬 coll.get() 回傳格式
        ids = [d["id"] for d in docs]
        documents = [d["content"] for d in docs]
        metadatas = [d.get("metadata", {}) for d in docs]
        coll.get.return_value = {
            "ids": ids,
            "documents": documents,
            "metadatas": metadatas,
        }
        return coll

    def test_basic_bm25_search(self, tmp_path, mock_llm):
        """基本 BM25 搜尋：jieba 分詞後應找到包含查詢詞的文件"""
        kb = KnowledgeBaseManager(str(tmp_path / "kb"), mock_llm)

        docs = [
            {"id": "1", "content": "這是一份關於環境保護的公文", "metadata": {}},
            {"id": "2", "content": "本函係為辦理人事異動事宜", "metadata": {}},
            {"id": "3", "content": "環境影響評估報告書審查結論", "metadata": {}},
        ]
        coll = self._make_mock_collection(docs)

        results = kb._bm25_search("環境保護", collections=[coll], n_results=5)

        # 至少應回傳包含「環境」和「保護」的文件
        assert len(results) > 0
        result_ids = [r["id"] for r in results]
        # 文件 1 和 3 都包含「環境」，應出現在結果中
        assert "1" in result_ids

    def test_bm25_returns_distance_and_score(self, tmp_path, mock_llm):
        """BM25 結果應包含 distance 和 _bm25_score 欄位"""
        kb = KnowledgeBaseManager(str(tmp_path / "kb"), mock_llm)

        docs = [
            {"id": "1", "content": "法規修正草案公告", "metadata": {}},
        ]
        coll = self._make_mock_collection(docs)

        results = kb._bm25_search("法規修正", collections=[coll], n_results=5)

        if results:
            assert "distance" in results[0]
            assert "_bm25_score" in results[0]
            assert results[0]["_bm25_score"] > 0

    def test_bm25_empty_collection(self, tmp_path, mock_llm):
        """空集合應回傳空結果"""
        kb = KnowledgeBaseManager(str(tmp_path / "kb"), mock_llm)

        coll = MagicMock()
        coll.name = "empty"
        coll.count.return_value = 0

        results = kb._bm25_search("測試查詢", collections=[coll], n_results=5)
        assert results == []

    def test_bm25_filters_by_source_level(self, tmp_path, mock_llm):
        """BM25 應根據 source_level 過濾文件"""
        kb = KnowledgeBaseManager(str(tmp_path / "kb"), mock_llm)

        docs = [
            {"id": "1", "content": "環境保護法規", "metadata": {"source_level": "A"}},
            {"id": "2", "content": "環境保護說明", "metadata": {"source_level": "B"}},
        ]
        coll = self._make_mock_collection(docs)

        results = kb._bm25_search(
            "環境保護", collections=[coll], n_results=5, source_level="A",
        )

        result_ids = [r["id"] for r in results]
        # 只有 source_level=A 的文件應出現
        assert "2" not in result_ids

    def test_bm25_filters_by_doc_type(self, tmp_path, mock_llm):
        """BM25 應根據 doc_type 過濾文件"""
        kb = KnowledgeBaseManager(str(tmp_path / "kb"), mock_llm)

        docs = [
            {"id": "1", "content": "函轉行政院修正通知", "metadata": {"doc_type": "函"}},
            {"id": "2", "content": "公告新修正法規通知", "metadata": {"doc_type": "公告"}},
        ]
        coll = self._make_mock_collection(docs)

        results = kb._bm25_search(
            "修正通知", collections=[coll], n_results=5, doc_type="函",
        )

        result_ids = [r["id"] for r in results]
        assert "2" not in result_ids

    def test_bm25_short_tokens_filtered(self, tmp_path, mock_llm):
        """長度 <= 1 的 token 應被過濾（停用詞級別）"""
        kb = KnowledgeBaseManager(str(tmp_path / "kb"), mock_llm)

        docs = [
            {"id": "1", "content": "這是完整的文件內容說明", "metadata": {}},
        ]
        coll = self._make_mock_collection(docs)

        # 查詢只有單字符詞，應全部被過濾掉
        results = kb._bm25_search("的", collections=[coll], n_results=5)
        assert results == []

    def test_bm25_multiple_collections(self, tmp_path, mock_llm):
        """BM25 應搜尋多個集合並合併結果。

        注意：BM25 IDF = log(N / (1 + df))，
        當查詢 token 出現在所有文件中且文件數很少時 IDF 為負數，
        因此需要足夠多的文件讓 IDF > 0（df < N - 1）。
        """
        kb = KnowledgeBaseManager(str(tmp_path / "kb"), mock_llm)

        # 集合 1：包含查詢詞「環境保護」的文件 + 不相關文件（提高 IDF）
        coll1 = self._make_mock_collection(
            [
                {"id": "c1_match", "content": "本機關辦理環境保護相關業務", "metadata": {}},
                {"id": "c1_other1", "content": "人事異動通知單", "metadata": {}},
                {"id": "c1_other2", "content": "年度預算審查報告", "metadata": {}},
            ],
            name="examples",
        )
        # 集合 2：包含查詢詞「環境保護」的文件 + 不相關文件
        coll2 = self._make_mock_collection(
            [
                {"id": "c2_match", "content": "環境保護法施行細則修正案", "metadata": {}},
                {"id": "c2_other1", "content": "工程採購招標須知", "metadata": {}},
                {"id": "c2_other2", "content": "交通運輸管理規章", "metadata": {}},
            ],
            name="regulations",
        )

        results = kb._bm25_search(
            "環境保護", collections=[coll1, coll2], n_results=10,
        )

        result_ids = [r["id"] for r in results]
        # 兩個集合中包含「環境保護」的文件都應出現在結果中
        assert len(results) >= 2
        assert "c1_match" in result_ids
        assert "c2_match" in result_ids

    def test_bm25_n_results_limit(self, tmp_path, mock_llm):
        """BM25 應遵守 n_results 限制"""
        kb = KnowledgeBaseManager(str(tmp_path / "kb"), mock_llm)

        docs = [
            {"id": str(i), "content": f"環境保護相關公文第{i}份", "metadata": {}}
            for i in range(20)
        ]
        coll = self._make_mock_collection(docs)

        results = kb._bm25_search("環境保護", collections=[coll], n_results=3)
        assert len(results) <= 3


class TestFormatQueryResults:
    """_format_query_results 靜態方法的單元測試"""

    def test_standard_chromadb_result(self):
        """標準 ChromaDB query() 回傳結構應正確格式化"""
        raw = {
            "ids": [["id1", "id2"]],
            "documents": [["文件一", "文件二"]],
            "metadatas": [[{"title": "T1"}, {"title": "T2"}]],
            "distances": [[0.1, 0.3]],
        }
        result = KnowledgeBaseManager._format_query_results(raw)

        assert len(result) == 2
        assert result[0]["id"] == "id1"
        assert result[0]["content"] == "文件一"
        assert result[0]["metadata"]["title"] == "T1"
        assert result[0]["distance"] == 0.1
        assert result[1]["id"] == "id2"
        assert result[1]["content"] == "文件二"
        assert result[1]["distance"] == 0.3

    def test_empty_results(self):
        """空的 ChromaDB 查詢結果應回傳空清單"""
        raw = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        result = KnowledgeBaseManager._format_query_results(raw)
        assert result == []

    def test_missing_ids(self):
        """缺少 ids 欄位應回傳空清單"""
        raw = {}
        result = KnowledgeBaseManager._format_query_results(raw)
        assert result == []

    def test_missing_documents(self):
        """缺少 documents 欄位時，content 應為空字串"""
        raw = {
            "ids": [["id1"]],
            "metadatas": [[{"key": "val"}]],
            "distances": [[0.2]],
        }
        result = KnowledgeBaseManager._format_query_results(raw)

        assert len(result) == 1
        assert result[0]["id"] == "id1"
        assert result[0]["content"] == ""

    def test_missing_metadatas(self):
        """缺少 metadatas 欄位時，metadata 應為空 dict"""
        raw = {
            "ids": [["id1"]],
            "documents": [["Doc"]],
            "distances": [[0.1]],
        }
        result = KnowledgeBaseManager._format_query_results(raw)

        assert len(result) == 1
        assert result[0]["metadata"] == {}

    def test_missing_distances(self):
        """缺少 distances 欄位時，distance 應為 None"""
        raw = {
            "ids": [["id1"]],
            "documents": [["Doc"]],
            "metadatas": [[{}]],
        }
        result = KnowledgeBaseManager._format_query_results(raw)

        assert len(result) == 1
        assert result[0]["distance"] is None

    def test_mismatched_lengths(self):
        """documents 和 ids 長度不匹配時應安全處理"""
        raw = {
            "ids": [["id1", "id2", "id3"]],
            "documents": [["Doc1"]],  # 只有 1 筆
            "metadatas": [[{"a": 1}]],  # 只有 1 筆
            "distances": [[0.1, 0.2]],  # 只有 2 筆
        }
        result = KnowledgeBaseManager._format_query_results(raw)

        assert len(result) == 3
        # 第 1 筆正常
        assert result[0]["content"] == "Doc1"
        assert result[0]["metadata"] == {"a": 1}
        assert result[0]["distance"] == 0.1
        # 第 2 筆：content 和 metadata 越界用預設值
        assert result[1]["content"] == ""
        assert result[1]["metadata"] == {}
        assert result[1]["distance"] == 0.2
        # 第 3 筆：全部越界用預設值
        assert result[2]["content"] == ""
        assert result[2]["metadata"] == {}
        assert result[2]["distance"] is None
