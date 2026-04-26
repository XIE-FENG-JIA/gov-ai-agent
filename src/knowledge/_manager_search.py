import logging
from contextlib import contextmanager
from typing import Any

import src.core.warnings_compat as warnings_compat


@contextmanager
def _noop_warning_suppression():
    yield


suppress_known_third_party_deprecations_temporarily = getattr(
    warnings_compat,
    "suppress_known_third_party_deprecations_temporarily",
    _noop_warning_suppression,
)

logger = logging.getLogger(__name__)

_KB_QUERY_EXCEPTIONS = (
    AttributeError,
    KeyError,
    RuntimeError,
    TypeError,
    ValueError,
    Exception,
)

_KB_DELETE_EXCEPTIONS = (
    AttributeError,
    KeyError,
    RuntimeError,
    TypeError,
    ValueError,
    Exception,
)


class KnowledgeSearchMixin:
    """搜尋與統計相關方法。"""

    @staticmethod
    def _format_query_results(results: dict) -> list[dict]:
        """將 ChromaDB query() 回傳的結果格式化為統一的 list[dict]。"""
        formatted: list[dict] = []
        if results.get("ids") and results["ids"][0]:
            ids_list = results["ids"][0]
            docs_list = results.get("documents", [[]])[0] if results.get("documents") else []
            metas_list = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
            dists_list = results.get("distances", [[]])[0] if results.get("distances") else []
            for i in range(len(ids_list)):
                formatted.append(
                    {
                        "id": ids_list[i],
                        "content": docs_list[i] if i < len(docs_list) else "",
                        "metadata": metas_list[i] if i < len(metas_list) else {},
                        "distance": dists_list[i] if i < len(dists_list) else None,
                    }
                )
        return formatted

    def search_policies(
        self,
        query: str,
        n_results: int = 3,
        source_level: str | None = None,
    ) -> list[dict]:
        """在政策集合中搜尋。"""
        if not self._available:
            logger.warning("知識庫不可用，無法搜尋政策。")
            return []
        query_embedding = self._cached_embed(query)
        if not query_embedding:
            logger.warning("政策搜尋查詢的嵌入向量為空，跳過搜尋")
            return []

        try:
            with suppress_known_third_party_deprecations_temporarily():
                count = self.policies_collection.count()
                if count == 0:
                    return []

                where_filter = {"source_level": source_level} if source_level else None
                results = self.policies_collection.query(
                    query_embeddings=[query_embedding],
                    n_results=min(n_results, count),
                    where=where_filter,
                )
        except _KB_QUERY_EXCEPTIONS as e:
            logger.warning("政策搜尋查詢失敗: %s", e)
            return []

        return self._format_query_results(results)

    def search_examples(
        self,
        query: str,
        n_results: int = 3,
        filter_metadata: dict | None = None,
        source_level: str | None = None,
    ) -> list[dict]:
        """搜尋相似的範例文件。"""
        if not self._available:
            logger.warning("知識庫不可用，無法搜尋範例。")
            return []
        query_embedding = self._cached_embed(query)

        if not query_embedding:
            logger.warning("範例搜尋查詢的嵌入向量為空，跳過搜尋")
            return []

        try:
            with suppress_known_third_party_deprecations_temporarily():
                count = self.examples_collection.count()
                if count == 0:
                    return []

                safe_filter = filter_metadata if filter_metadata else None
                if source_level:
                    level_filter = {"source_level": source_level}
                    if safe_filter:
                        safe_filter = {"$and": [safe_filter, level_filter]}
                    else:
                        safe_filter = level_filter
                results = self.examples_collection.query(
                    query_embeddings=[query_embedding],
                    n_results=min(n_results, count),
                    where=safe_filter,
                )
        except _KB_QUERY_EXCEPTIONS as e:
            logger.warning("範例搜尋查詢失敗: %s", e)
            return []

        return self._format_query_results(results)

    def search_regulations(
        self,
        query: str,
        doc_type: str | None = None,
        n_results: int = 3,
        source_level: str | None = None,
    ) -> list[dict]:
        """在法規集合中搜尋，可依公文類型或來源等級篩選。"""
        if not self._available:
            logger.warning("知識庫不可用，無法搜尋法規。")
            return []
        query_embedding = self._cached_embed(query)
        if not query_embedding:
            logger.warning("法規搜尋查詢的嵌入向量為空，跳過搜尋")
            return []

        try:
            with suppress_known_third_party_deprecations_temporarily():
                count = self.regulations_collection.count()
                if count == 0:
                    return []

                conditions: list[dict] = []
                if doc_type:
                    conditions.append({"doc_type": doc_type})
                if source_level:
                    conditions.append({"source_level": source_level})

                if len(conditions) > 1:
                    where_filter = {"$and": conditions}
                elif len(conditions) == 1:
                    where_filter = conditions[0]
                else:
                    where_filter = None

                results = self.regulations_collection.query(
                    query_embeddings=[query_embedding],
                    n_results=min(n_results, count),
                    where=where_filter,
                )
        except _KB_QUERY_EXCEPTIONS as e:
            logger.warning("法規搜尋查詢失敗: %s", e)
            return []

        return self._format_query_results(results)

    def search_level_a(self, query: str, n_results: int = 3) -> list[dict]:
        """僅搜尋 Level A 權威來源（法規+公報）。"""
        results: list[dict] = []
        results.extend(self.search_regulations(query, source_level="A", n_results=n_results))
        results.extend(self.search_examples(query, source_level="A", n_results=n_results))
        results.sort(key=lambda x: x.get("distance") or 1.0)
        return results[:n_results]

    def get_stats(self) -> dict[str, int]:
        """取得集合統計資訊。"""
        if not self._available:
            return {
                "examples_count": 0,
                "regulations_count": 0,
                "policies_count": 0,
            }
        with suppress_known_third_party_deprecations_temporarily():
            return {
                "examples_count": self.examples_collection.count(),
                "regulations_count": self.regulations_collection.count(),
                "policies_count": self.policies_collection.count(),
            }

    def reset_db(self) -> None:
        """危險操作：重設資料庫（刪除所有集合後重建）。"""
        if not self._available:
            logger.warning("知識庫不可用，無法重設。")
            return
        collection_names = ["public_doc_examples", "regulations", "policies"]
        for name in collection_names:
            try:
                with suppress_known_third_party_deprecations_temporarily():
                    self.client.delete_collection(name)
            except _KB_DELETE_EXCEPTIONS as e:
                logger.warning("集合 %s 不存在或刪除失敗，跳過刪除: %s", name, e)
        with suppress_known_third_party_deprecations_temporarily():
            new_examples = self.client.get_or_create_collection(
                name="public_doc_examples",
                metadata={"hnsw:space": "cosine"},
            )
            new_regulations = self.client.get_or_create_collection(
                name="regulations",
                metadata={"hnsw:space": "cosine"},
            )
            new_policies = self.client.get_or_create_collection(
                name="policies",
                metadata={"hnsw:space": "cosine"},
            )
        self.examples_collection = new_examples
        self.regulations_collection = new_regulations
        self.policies_collection = new_policies
        self.invalidate_cache()

    @staticmethod
    def _rrf_fuse(
        vector_results: list[dict],
        bm25_results: list[dict],
        n_results: int,
        k: int = 60,
    ) -> list[dict]:
        """用 Reciprocal Rank Fusion 融合向量搜尋和 BM25 搜尋的排名。"""
        doc_map: dict[str, dict] = {}
        rrf_scores: dict[str, float] = {}

        vector_sorted = sorted(vector_results, key=lambda x: x.get("distance") or 1.0)
        for rank, doc in enumerate(vector_sorted):
            doc_id = doc["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            if doc_id not in doc_map:
                doc_map[doc_id] = doc

        for rank, doc in enumerate(bm25_results):
            doc_id = doc["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            if doc_id not in doc_map:
                doc_map[doc_id] = doc

        sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)

        results: list[dict] = []
        for doc_id in sorted_ids[:n_results]:
            doc = doc_map[doc_id].copy()
            doc["_rrf_score"] = rrf_scores[doc_id]
            doc.pop("_bm25_score", None)
            results.append(doc)

        return results

    def add_example(self, content: str, metadata: dict[str, Any]) -> str | None:
        """相容性包裝函式，呼叫 add_document。"""
        return self.add_document(content, metadata, "examples")
