import logging
import math
from collections import Counter
from contextlib import contextmanager
from typing import Any

import src.core.warnings_compat as warnings_compat
from src.knowledge._bm25_scoring import bm25_search_docs, tfidf_search_docs


@contextmanager
def _noop_warning_suppression():
    yield


suppress_known_third_party_deprecations_temporarily = getattr(
    warnings_compat,
    "suppress_known_third_party_deprecations_temporarily",
    _noop_warning_suppression,
)

logger = logging.getLogger(__name__)
_KB_HYBRID_EXCEPTIONS = (AttributeError, KeyError, RuntimeError, TypeError, ValueError, Exception)


class KnowledgeHybridSearchMixin:
    """Hybrid search 與文件拉取相關方法。"""

    def search_hybrid(
        self,
        query: str,
        n_results: int = 5,
        source_level: str | None = None,
        doc_type: str | None = None,
        source_type: str | None = None,
    ) -> list[dict]:
        """Hybrid Search：向量語意搜尋 + BM25 關鍵字搜尋，以 RRF 融合排序。"""
        if not self._available:
            logger.warning("知識庫不可用，無法執行混合搜尋。")
            return []

        cache_key = (query, n_results, source_level, doc_type, source_type)
        with self._cache_lock:
            cached = self._search_cache.get(cache_key)
        if cached is not None:
            logger.debug("混合搜尋快取命中: query=%s", query[:30])
            return cached

        query_embedding = self._cached_embed(query)
        if not query_embedding:
            logger.warning("混合搜尋嵌入向量為空，降級至關鍵字搜尋")
            result = self._keyword_fallback_search(
                query, n_results, source_level, doc_type, source_type
            )
            with self._cache_lock:
                self._search_cache[cache_key] = result
            return result

        conditions: list[dict] = []
        if source_level:
            conditions.append({"source_level": source_level})
        if doc_type:
            conditions.append({"doc_type": doc_type})
        if source_type:
            conditions.append({"source": source_type})

        if len(conditions) > 1:
            where_filter: dict | None = {"$and": conditions}
        elif len(conditions) == 1:
            where_filter = conditions[0]
        else:
            where_filter = None

        vector_results: list[dict] = []
        collections = [
            self.examples_collection,
            self.regulations_collection,
            self.policies_collection,
        ]
        vector_fetch = n_results * 2

        for coll in collections:
            try:
                with suppress_known_third_party_deprecations_temporarily():
                    count = coll.count()
                    if count == 0:
                        continue
                    results = coll.query(
                        query_embeddings=[query_embedding],
                        n_results=min(vector_fetch, count),
                        where=where_filter,
                    )
                vector_results.extend(self._format_query_results(results))
            except _KB_HYBRID_EXCEPTIONS as e:
                logger.warning("混合搜尋向量查詢失敗: %s", e)
                continue

        bm25_results: list[dict] = []
        try:
            bm25_results = self._bm25_search(
                query,
                collections=collections,
                n_results=vector_fetch,
                source_level=source_level,
                doc_type=doc_type,
                source_type=source_type,
            )
        except _KB_HYBRID_EXCEPTIONS as e:
            logger.warning("混合搜尋 BM25 查詢失敗，回退至純向量搜尋: %s", e)

        if bm25_results:
            final = self._rrf_fuse(vector_results, bm25_results, n_results)
            logger.info(
                "Hybrid search: 向量 %d 筆 + BM25 %d 筆 → 融合 %d 筆",
                len(vector_results),
                len(bm25_results),
                len(final),
            )
        else:
            vector_results.sort(key=lambda x: x.get("distance") or 1.0)
            final = vector_results[:n_results]
            logger.info(
                "Hybrid search: 向量 %d 筆 + BM25 0 筆 → 純向量 %d 筆",
                len(vector_results),
                len(final),
            )

        with self._cache_lock:
            self._search_cache[cache_key] = final
        return final

    def _fetch_filtered_docs(
        self,
        collections: list,
        source_level: str | None = None,
        doc_type: str | None = None,
        source_type: str | None = None,
    ) -> list[dict]:
        """從多個 ChromaDB 集合拉取文件並篩選 metadata，帶 TTL 快取。"""

        def _coll_name(coll: Any) -> str:
            name = getattr(coll, "name", "")
            return name if isinstance(name, str) else str(name)

        coll_names = tuple(sorted(_coll_name(c) for c in collections))
        cache_key = (coll_names, source_level, doc_type, source_type)

        with self._doc_cache_lock:
            cached = self._doc_cache.get(cache_key)
        if cached is not None:
            return cached

        all_docs: list[dict] = []
        for coll in collections:
            coll_name = _coll_name(coll)
            try:
                with suppress_known_third_party_deprecations_temporarily():
                    count = coll.count()
                    if count == 0:
                        continue
                    if count > 500:
                        logger.debug("集合 %s 文件數 %d > 500，僅取前 500 筆", coll_name, count)
                    data = coll.get(include=["documents", "metadatas"], limit=500)
                if not data or not data.get("ids"):
                    continue
                for i, doc_id in enumerate(data["ids"]):
                    content = (
                        data["documents"][i]
                        if data.get("documents") and i < len(data["documents"])
                        else ""
                    )
                    meta = (
                        data["metadatas"][i]
                        if data.get("metadatas") and i < len(data["metadatas"])
                        else {}
                    )
                    if source_level and meta.get("source_level") != source_level:
                        continue
                    if doc_type and meta.get("doc_type") != doc_type:
                        continue
                    if source_type and meta.get("source") != source_type:
                        continue
                    all_docs.append({"id": doc_id, "content": content, "metadata": meta})
            except _KB_HYBRID_EXCEPTIONS as e:
                logger.warning("集合文件拉取失敗 (%s): %s", coll_name, e)
                continue

        with self._doc_cache_lock:
            self._doc_cache[cache_key] = all_docs
        return all_docs

    def _bm25_search(
        self,
        query: str,
        collections: list,
        n_results: int = 10,
        source_level: str | None = None,
        doc_type: str | None = None,
        source_type: str | None = None,
    ) -> list[dict]:
        """使用 jieba 分詞 + 簡化 BM25 評分進行關鍵字搜尋。

        query 超過 500 字時截短 — 實際使用者搜尋不會那麼長，過長 query 讓
        jieba.cut 成為效能漏洞（30k 字 query 約 8s；也是 DoS 向量）。
        截短不改變 BM25 語意：前 500 字已含足夠 token 做相關性排序。
        """
        try:
            import jieba  # noqa: F401
        except ImportError:
            logger.debug("jieba 未安裝，跳過 BM25 搜尋")
            return []

        # Early-exit before jieba init when no docs exist — avoids 5-7s jieba
        # cold-start for empty KB / mock collections.
        all_docs = self._fetch_filtered_docs(collections, source_level, doc_type, source_type)
        if not all_docs:
            return []

        return bm25_search_docs(query, all_docs, n_results)

    def _keyword_fallback_search(
        self,
        query: str,
        n_results: int = 5,
        source_level: str | None = None,
        doc_type: str | None = None,
        source_type: str | None = None,
    ) -> list[dict]:
        """當 embedding 失敗時，使用 jieba 分詞 + TF-IDF 進行關鍵字搜尋。"""
        try:
            import jieba  # noqa: F401
        except ImportError:
            logger.warning("jieba 未安裝，無法執行關鍵字降級搜尋")
            return []

        collections = [
            self.examples_collection,
            self.regulations_collection,
            self.policies_collection,
        ]
        all_docs = self._fetch_filtered_docs(collections, source_level, doc_type, source_type)
        if not all_docs:
            return []

        results = tfidf_search_docs(query, all_docs, n_results)
        logger.info("關鍵字降級搜尋完成: 查詢=%s, 結果=%d 筆", query[:30], len(results))
        return results
