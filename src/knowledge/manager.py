import logging
import math
import threading
from collections import Counter
from typing import Any
import uuid

from cachetools import TTLCache

from src.core.llm import LLMProvider

try:
    import chromadb
except ImportError:
    chromadb = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# 搜尋快取設定
_CACHE_TTL = 300       # 5 分鐘
_CACHE_MAXSIZE = 256   # 最多快取 256 筆查詢

# Embedding 快取設定（避免同一 query 在多輪審查中重複呼叫 LLM embed）
_EMBED_CACHE_TTL = 600     # 10 分鐘（比搜尋快取長，因為向量不隨知識庫變動）
_EMBED_CACHE_MAXSIZE = 128  # 最多快取 128 筆 embedding

class KnowledgeBaseManager:
    """管理本地 ChromaDB 知識庫。"""

    def __init__(
        self,
        persist_path: str,
        llm_provider: LLMProvider,
        contextual_retrieval: bool = False,
    ) -> None:
        self.persist_path = persist_path
        self.llm_provider = llm_provider
        self.contextual_retrieval = contextual_retrieval
        self._available = True
        # 搜尋快取（TTL 5 分鐘，最多 256 筆）
        self._search_cache: TTLCache = TTLCache(maxsize=_CACHE_MAXSIZE, ttl=_CACHE_TTL)
        self._cache_lock = threading.Lock()
        # Embedding 快取：同一 query 在多輪審查中不重複呼叫 LLM embed
        self._embed_cache: TTLCache = TTLCache(maxsize=_EMBED_CACHE_MAXSIZE, ttl=_EMBED_CACHE_TTL)
        self._embed_cache_lock = threading.Lock()

        if chromadb is None:
            logger.error(
                "chromadb 未安裝，知識庫功能不可用。請執行: pip install chromadb"
            )
            self._available = False
            self.client = None
            self.examples_collection = None
            self.regulations_collection = None
            self.policies_collection = None
            return

        try:
            self.client = chromadb.PersistentClient(path=persist_path)

            # Initialize collections
            self.examples_collection = self.client.get_or_create_collection(
                name="public_doc_examples",
                metadata={"hnsw:space": "cosine"}
            )

            self.regulations_collection = self.client.get_or_create_collection(
                name="regulations",
                metadata={"hnsw:space": "cosine"}
            )

            self.policies_collection = self.client.get_or_create_collection(
                name="policies",
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            logger.error(
                "知識庫初始化失敗（路徑: %s）: %s。系統將以無知識庫模式運作。",
                persist_path, e,
            )
            self._available = False
            self.client = None
            self.examples_collection = None
            self.regulations_collection = None
            self.policies_collection = None

    def _cached_embed(self, query: str) -> list[float]:
        """帶 TTL 快取的 embedding 呼叫。

        同一 query 在快取有效期內（10 分鐘）直接返回向量，
        避免多輪審查中對同一搜尋詞重複呼叫 LLM embed API。
        """
        with self._embed_cache_lock:
            cached = self._embed_cache.get(query)
        if cached is not None:
            return cached
        embedding = self.llm_provider.embed(query)
        if embedding:
            with self._embed_cache_lock:
                self._embed_cache[query] = embedding
        return embedding

    def add_document(
        self,
        content: str,
        metadata: dict[str, Any],
        collection_name: str = "examples",
        full_document: str | None = None,
        chunk_index: int | None = None,
        total_chunks: int | None = None,
    ) -> str | None:
        """將文件新增至指定的集合。

        Args:
            content: 要匯入的文字內容（單一 chunk）。
            metadata: ChromaDB 相容的 metadata 字典。
            collection_name: 目標集合名稱。
            full_document: 完整原始文件內容（供 Contextual Retrieval 使用）。
            chunk_index: 此 chunk 在原始文件中的索引（從 0 開始）。
            total_chunks: 原始文件的 chunk 總數。
        """
        if not self._available:
            logger.warning("知識庫不可用，無法新增文件。")
            return None

        # 防護空值內容
        if not content or not content.strip():
            logger.warning("無法新增空白內容的文件")
            return None

        # Contextual Retrieval：為 chunk 加入上下文摘要前綴
        if self.contextual_retrieval and full_document:
            idx = chunk_index if chunk_index is not None else 0
            total = total_chunks if total_chunks is not None else 1
            content = self._enrich_with_context(content, full_document, idx, total)

        doc_id = str(uuid.uuid4())

        # Generate embedding using our LLM provider
        embedding = self.llm_provider.embed(content)

        if not embedding:
            logger.warning("無法產生文件的嵌入向量: %s", metadata.get('title', '未知'))
            return None

        if collection_name == "regulations":
            target_collection = self.regulations_collection
        elif collection_name == "policies":
            target_collection = self.policies_collection
        else:
            target_collection = self.examples_collection

        try:
            target_collection.add(
                documents=[content],
                embeddings=[embedding],
                metadatas=[metadata],
                ids=[doc_id]
            )
        except Exception as e:
            logger.error("文件寫入知識庫失敗: %s", e)
            return None
        # 新增文件後清除快取，確保後續搜尋能看到新資料
        self.invalidate_cache()
        return doc_id

    # ------------------------------------------------------------------
    # Contextual Retrieval — 為每個 chunk 加入上下文摘要前綴
    # ------------------------------------------------------------------

    def _enrich_with_context(
        self, chunk: str, full_doc: str, idx: int, total: int
    ) -> str:
        """為 chunk 加入上下文摘要前綴（Contextual Retrieval）。

        使用 LLM 生成一段簡短描述，說明此 chunk 在完整文件中的角色，
        然後以 ``[上下文: ...]`` 前綴的形式附加在 chunk 開頭。
        這能讓 embedding 更準確地理解 chunk 的語境，降低檢索錯誤率。

        若 LLM 呼叫失敗或回傳不合理內容，會 graceful fallback 到原始 chunk。
        """
        if not self.llm_provider:
            return chunk

        prompt = (
            f"以下是一份完整公文的第 {idx + 1}/{total} 段。"
            "請用一句話（30字內）描述這段內容在整份公文中的角色和上下文。"
            "只輸出描述，不要任何其他文字。\n\n"
            f"【完整公文摘要】{full_doc[:500]}\n\n"
            f"【本段內容】{chunk}"
        )
        try:
            context = self.llm_provider.generate(prompt, temperature=0.1, max_tokens=80)
            if context and len(context.strip()) < 100:
                enriched = f"[上下文: {context.strip()}] {chunk}"
                logger.debug(
                    "Contextual enrichment 完成 (chunk %d/%d): %s",
                    idx + 1, total, context.strip()[:50],
                )
                return enriched
            logger.debug("Contextual enrichment 回傳過長或為空，使用原始 chunk")
        except Exception as e:
            logger.warning("Contextual enrichment 失敗，使用原始 chunk: %s", e)
        return chunk

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
                formatted.append({
                    "id": ids_list[i],
                    "content": docs_list[i] if i < len(docs_list) else "",
                    "metadata": metas_list[i] if i < len(metas_list) else {},
                    "distance": dists_list[i] if i < len(dists_list) else None,
                })
        return formatted

    @property
    def is_available(self) -> bool:
        """知識庫是否可用。"""
        return self._available

    def invalidate_cache(self) -> None:
        """清除搜尋快取。在 ingest / reset 後呼叫以確保資料一致性。"""
        with self._cache_lock:
            self._search_cache.clear()
        logger.debug("搜尋快取已清除")

    def search_policies(self, query: str, n_results: int = 3, source_level: str | None = None) -> list[dict]:
        """在政策集合中搜尋。"""
        if not self._available:
            logger.warning("知識庫不可用，無法搜尋政策。")
            return []
        query_embedding = self._cached_embed(query)
        if not query_embedding:
            logger.warning("政策搜尋查詢的嵌入向量為空，跳過搜尋")
            return []

        try:
            count = self.policies_collection.count()
            if count == 0:
                return []

            where_filter = {"source_level": source_level} if source_level else None
            results = self.policies_collection.query(
                query_embeddings=[query_embedding],
                n_results=min(n_results, count),
                where=where_filter,
            )
        except Exception as e:
            logger.error("政策搜尋查詢失敗: %s", e)
            return []

        return self._format_query_results(results)

    def search_examples(
        self, query: str, n_results: int = 3,
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
            count = self.examples_collection.count()
            if count == 0:
                return []

            # 正規化空字典為 None，避免 ChromaDB 拒絕空 where 條件
            safe_filter = filter_metadata if filter_metadata else None
            # 合併 source_level 篩選條件
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
        except Exception as e:
            logger.error("範例搜尋查詢失敗: %s", e)
            return []

        return self._format_query_results(results)

    def search_regulations(
        self, query: str, doc_type: str | None = None,
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
        except Exception as e:
            logger.error("法規搜尋查詢失敗: %s", e)
            return []

        return self._format_query_results(results)

    def search_hybrid(
        self,
        query: str,
        n_results: int = 5,
        source_level: str | None = None,
        doc_type: str | None = None,
        source_type: str | None = None,
    ) -> list[dict]:
        """Hybrid Search：向量語意搜尋 + BM25 關鍵字搜尋，以 RRF 融合排序。

        搜尋 examples + regulations + policies 三個集合，
        對每個集合同時做向量搜尋與 BM25 關鍵字搜尋，
        再用 Reciprocal Rank Fusion (RRF) 融合兩個排名取 top-N。

        包含 TTL 快取（5 分鐘）和 embedding 失敗時的關鍵字降級搜尋。
        """
        if not self._available:
            logger.warning("知識庫不可用，無法執行混合搜尋。")
            return []

        # 快取查詢：以參數 tuple 為 key
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
                query, n_results, source_level, doc_type, source_type,
            )
            with self._cache_lock:
                self._search_cache[cache_key] = result
            return result

        # 建構 where 條件
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

        # --- 向量搜尋 ---
        vector_results: list[dict] = []
        collections = [
            self.examples_collection,
            self.regulations_collection,
            self.policies_collection,
        ]

        # 向量搜尋取較多結果以便 RRF 融合（每集合取 n_results * 2）
        vector_fetch = n_results * 2

        for coll in collections:
            try:
                count = coll.count()
                if count == 0:
                    continue
                results = coll.query(
                    query_embeddings=[query_embedding],
                    n_results=min(vector_fetch, count),
                    where=where_filter,
                )
                vector_results.extend(self._format_query_results(results))
            except Exception as e:
                logger.warning("混合搜尋向量查詢失敗: %s", e)
                continue

        # --- BM25 關鍵字搜尋 ---
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
        except Exception as e:
            logger.warning("混合搜尋 BM25 查詢失敗，回退至純向量搜尋: %s", e)

        # --- RRF 融合 ---
        if bm25_results:
            final = self._rrf_fuse(vector_results, bm25_results, n_results)
            logger.info(
                "Hybrid search: 向量 %d 筆 + BM25 %d 筆 → 融合 %d 筆",
                len(vector_results), len(bm25_results), len(final),
            )
        else:
            # BM25 無結果，回退至純向量排序
            vector_results.sort(key=lambda x: x.get("distance") or 1.0)
            final = vector_results[:n_results]
            logger.info(
                "Hybrid search: 向量 %d 筆 + BM25 0 筆 → 純向量 %d 筆",
                len(vector_results), len(final),
            )

        # 寫入快取
        with self._cache_lock:
            self._search_cache[cache_key] = final
        return final

    # ------------------------------------------------------------------
    # BM25 關鍵字搜尋（Hybrid Search 用）
    # ------------------------------------------------------------------

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

        BM25 公式（簡化版）:
            score = sum(tf(t,d) * idf(t) for t in query_terms)
            tf(t,d) = freq(t,d) / len(d)
            idf(t) = log(N / (1 + df(t)))
        """
        try:
            import jieba
        except ImportError:
            logger.debug("jieba 未安裝，跳過 BM25 搜尋")
            return []

        query_tokens = list(jieba.cut(query))
        # 過濾掉長度 <= 1 的停用詞級別 token
        query_tokens = [t for t in query_tokens if len(t.strip()) > 1]
        if not query_tokens:
            return []

        # 從所有集合取出文件
        all_docs: list[dict] = []
        for coll in collections:
            try:
                count = coll.count()
                if count == 0:
                    continue
                if count > 500:
                    logger.debug(
                        "BM25: 集合 %s 文件數 %d > 500，僅取前 500 筆",
                        coll.name, count,
                    )
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
                    # metadata 篩選
                    if source_level and meta.get("source_level") != source_level:
                        continue
                    if doc_type and meta.get("doc_type") != doc_type:
                        continue
                    if source_type and meta.get("source") != source_type:
                        continue

                    all_docs.append({
                        "id": doc_id,
                        "content": content,
                        "metadata": meta,
                    })
            except Exception as e:
                logger.warning("BM25 集合讀取失敗: %s", e)
                continue

        if not all_docs:
            return []

        # 對每篇文件做 jieba 分詞並計算詞頻
        doc_count = len(all_docs)
        token_doc_freq: Counter = Counter()  # df(t): 包含 token t 的文件數
        doc_token_freqs: list[Counter] = []  # 每篇文件的詞頻 Counter
        doc_lengths: list[int] = []          # 每篇文件的 token 總數

        for doc in all_docs:
            tokens = list(jieba.cut(doc["content"]))
            freq = Counter(tokens)
            doc_token_freqs.append(freq)
            doc_lengths.append(len(tokens))
            for unique_token in freq:
                token_doc_freq[unique_token] += 1

        # 計算 BM25 分數
        scored: list[tuple[float, dict]] = []
        for idx, doc in enumerate(all_docs):
            freq = doc_token_freqs[idx]
            doc_len = doc_lengths[idx] if doc_lengths[idx] > 0 else 1
            score = 0.0
            for qt in query_tokens:
                if qt in freq:
                    tf = freq[qt] / doc_len
                    df = token_doc_freq.get(qt, 0)
                    idf = math.log((doc_count) / (1 + df))
                    score += tf * idf
            scored.append((score, doc))

        # 依分數降序排序，取 top-N（分數 > 0）
        scored.sort(key=lambda x: x[0], reverse=True)
        results: list[dict] = []
        for score, doc in scored[:n_results]:
            if score > 0:
                doc["distance"] = 1.0 / (1.0 + score)  # 轉換為距離格式
                doc["_bm25_score"] = score
                results.append(doc)

        return results

    # ------------------------------------------------------------------
    # Reciprocal Rank Fusion (RRF)
    # ------------------------------------------------------------------

    @staticmethod
    def _rrf_fuse(
        vector_results: list[dict],
        bm25_results: list[dict],
        n_results: int,
        k: int = 60,
    ) -> list[dict]:
        """用 Reciprocal Rank Fusion 融合向量搜尋和 BM25 搜尋的排名。

        RRF 公式: rrf_score(d) = sum(1 / (k + rank_i) for each ranking)
        其中 k=60 是標準常數。
        """
        # 建立 id → doc 的對應（用於去重和合併）
        doc_map: dict[str, dict] = {}
        rrf_scores: dict[str, float] = {}

        # 向量搜尋排名（已按 distance 排序，distance 越小越好）
        vector_sorted = sorted(vector_results, key=lambda x: x.get("distance") or 1.0)
        for rank, doc in enumerate(vector_sorted):
            doc_id = doc["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            if doc_id not in doc_map:
                doc_map[doc_id] = doc

        # BM25 排名（已按 _bm25_score 降序排序）
        for rank, doc in enumerate(bm25_results):
            doc_id = doc["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            if doc_id not in doc_map:
                doc_map[doc_id] = doc

        # 按 RRF 分數降序排序
        sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)

        results: list[dict] = []
        for doc_id in sorted_ids[:n_results]:
            doc = doc_map[doc_id].copy()
            doc["_rrf_score"] = rrf_scores[doc_id]
            # 清理 BM25 內部欄位
            doc.pop("_bm25_score", None)
            results.append(doc)

        return results

    # ------------------------------------------------------------------
    # Embedding 失敗降級：關鍵字搜尋（jieba 分詞 + TF-IDF）
    # ------------------------------------------------------------------

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
            import jieba
        except ImportError:
            logger.warning("jieba 未安裝，無法執行關鍵字降級搜尋")
            return []

        query_tokens = set(jieba.cut(query))
        if not query_tokens:
            return []

        # 從所有集合取出全部文件
        all_docs: list[dict] = []
        collections = [
            self.examples_collection,
            self.regulations_collection,
            self.policies_collection,
        ]
        for coll in collections:
            try:
                count = coll.count()
                if count == 0:
                    continue
                if count > 500:
                    logger.info("集合 %s 文件數 %d > 500，關鍵字搜尋僅取前 500 筆", coll.name, count)
                # ChromaDB get() 取出文件（限制最多 500 筆避免記憶體爆量）
                data = coll.get(include=["documents", "metadatas"], limit=500)
                if not data or not data.get("ids"):
                    continue
                for i, doc_id in enumerate(data["ids"]):
                    content = data["documents"][i] if data.get("documents") and i < len(data["documents"]) else ""
                    meta = data["metadatas"][i] if data.get("metadatas") and i < len(data["metadatas"]) else {}

                    # metadata 篩選
                    if source_level and meta.get("source_level") != source_level:
                        continue
                    if doc_type and meta.get("doc_type") != doc_type:
                        continue
                    if source_type and meta.get("source") != source_type:
                        continue

                    all_docs.append({
                        "id": doc_id,
                        "content": content,
                        "metadata": meta,
                    })
            except Exception as e:
                logger.warning("關鍵字搜尋集合讀取失敗: %s", e)
                continue

        if not all_docs:
            return []

        # 計算 TF-IDF 相似度
        # 先建立 IDF（逆文件頻率）
        doc_count = len(all_docs)
        token_doc_freq: Counter = Counter()
        doc_tokens_list: list[set[str]] = []
        for doc in all_docs:
            tokens = set(jieba.cut(doc["content"]))
            doc_tokens_list.append(tokens)
            for token in tokens:
                token_doc_freq[token] += 1

        scored: list[tuple[float, dict]] = []
        for idx, doc in enumerate(all_docs):
            doc_tokens = doc_tokens_list[idx]
            score = 0.0
            for qt in query_tokens:
                if qt in doc_tokens:
                    # TF-IDF: tf=1（布林型）, idf=log(N/df)
                    df = token_doc_freq.get(qt, 1)
                    score += math.log((doc_count + 1) / (df + 1))
            scored.append((score, doc))

        # 依分數降序排序
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, doc in scored[:n_results]:
            if score > 0:
                doc["distance"] = 1.0 / (1.0 + score)  # 轉換為距離（越小越好）
                results.append(doc)

        logger.info("關鍵字降級搜尋完成: 查詢=%s, 結果=%d 筆", query[:30], len(results))
        return results

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
        return {
            "examples_count": self.examples_collection.count(),
            "regulations_count": self.regulations_collection.count(),
            "policies_count": self.policies_collection.count()
        }

    def reset_db(self) -> None:
        """危險操作：重設資料庫（刪除所有集合後重建）。

        使用原子更新模式：先建立全部新集合，全部成功後才替換實例屬性，
        避免部分失敗導致知識庫進入損壞狀態。
        """
        if not self._available:
            logger.warning("知識庫不可用，無法重設。")
            return
        collection_names = ["public_doc_examples", "regulations", "policies"]
        for name in collection_names:
            try:
                self.client.delete_collection(name)
            except Exception as e:
                logger.debug("集合 %s 不存在，跳過刪除: %s", name, e)
        # 重建集合（使用臨時變數，全部成功才原子替換）
        new_examples = self.client.get_or_create_collection(
            name="public_doc_examples", metadata={"hnsw:space": "cosine"}
        )
        new_regulations = self.client.get_or_create_collection(
            name="regulations", metadata={"hnsw:space": "cosine"}
        )
        new_policies = self.client.get_or_create_collection(
            name="policies", metadata={"hnsw:space": "cosine"}
        )
        # 全部成功才替換
        self.examples_collection = new_examples
        self.regulations_collection = new_regulations
        self.policies_collection = new_policies
        # 重設後清除快取
        self.invalidate_cache()

    def add_example(self, content: str, metadata: dict[str, Any]) -> str | None:
        """相容性包裝函式，呼叫 add_document。"""
        return self.add_document(content, metadata, "examples")
