import hashlib
import importlib
import logging
import threading
from contextlib import contextmanager
from typing import Any
import uuid

from cachetools import TTLCache

from src.core.llm import LLMProvider
import src.core.warnings_compat as warnings_compat
from src.knowledge._manager_hybrid import KnowledgeHybridSearchMixin
from src.knowledge._manager_search import KnowledgeSearchMixin


@contextmanager
def _noop_warning_suppression():
    yield


suppress_known_third_party_deprecations = warnings_compat.suppress_known_third_party_deprecations
suppress_known_third_party_deprecations_temporarily = getattr(
    warnings_compat,
    "suppress_known_third_party_deprecations_temporarily",
    _noop_warning_suppression,
)

suppress_known_third_party_deprecations()

try:
    import chromadb
except ImportError:
    chromadb = None  # type: ignore[assignment]
_CHROMADB_IMPORT_FAILED = chromadb is None

logger = logging.getLogger(__name__)
_KB_MANAGER_EXCEPTIONS = (
    AttributeError,
    KeyError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
# ChromaDB / mocks / 損壞的 persisted state 可能丟出未細分的 vendor exception；
# KnowledgeBaseManager 的契約是「降級不中斷」，因此統一收斂成 warning/error fallback。
_KB_MANAGER_VENDOR_EXCEPTIONS = _KB_MANAGER_EXCEPTIONS + (
    Exception,
)

# 搜尋快取設定
_CACHE_TTL = 300       # 5 分鐘
_CACHE_MAXSIZE = 256   # 最多快取 256 筆查詢

# Embedding 快取設定（避免同一 query 在多輪審查中重複呼叫 LLM embed）
_EMBED_CACHE_TTL = 600     # 10 分鐘（比搜尋快取長；invalidate_cache() 會主動清除）
_EMBED_CACHE_MAXSIZE = 128  # 最多快取 128 筆 embedding

# 文件集合快取設定（BM25/keyword 搜尋用，避免每次重新從 ChromaDB 拉取全量文件）
_DOC_CACHE_TTL = 60        # 1 分鐘（文件可能被新增，不宜太長）
_DOC_CACHE_MAXSIZE = 32    # 按 (集合組合, 篩選條件) 快取


def _log_kb_warning(action: str, exc: Exception) -> None:
    """記錄可預期的知識庫降級錯誤。"""
    logger.warning("%s 失敗: %s", action, exc)


def _resolve_chromadb() -> Any:
    """解析 chromadb 模組。

    只有在模組載入當下因 ImportError 缺失時才重試 import；
    若執行期間被測試或呼叫端明確設為 None，視為不可用。
    """
    global chromadb, _CHROMADB_IMPORT_FAILED
    if chromadb is not None:
        return chromadb
    if not _CHROMADB_IMPORT_FAILED:
        return None
    try:
        chromadb = importlib.import_module("chromadb")
        _CHROMADB_IMPORT_FAILED = False
    except ImportError:
        chromadb = None  # type: ignore[assignment]
        _CHROMADB_IMPORT_FAILED = True
    return chromadb


class KnowledgeBaseManager(KnowledgeHybridSearchMixin, KnowledgeSearchMixin):
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
        # 文件集合快取：BM25/keyword 搜尋避免每次從 ChromaDB 拉取全量文件
        self._doc_cache: TTLCache = TTLCache(maxsize=_DOC_CACHE_MAXSIZE, ttl=_DOC_CACHE_TTL)
        self._doc_cache_lock = threading.Lock()

        chromadb_module = _resolve_chromadb()
        if chromadb_module is None:
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
            with suppress_known_third_party_deprecations_temporarily():
                self.client = chromadb_module.PersistentClient(path=persist_path)
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
        except _KB_MANAGER_VENDOR_EXCEPTIONS as e:
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
            with suppress_known_third_party_deprecations_temporarily():
                target_collection.add(
                    documents=[content],
                    embeddings=[embedding],
                    metadatas=[metadata],
                    ids=[doc_id]
                )
        except _KB_MANAGER_VENDOR_EXCEPTIONS as e:
            logger.error("文件寫入知識庫失敗: %s", e)
            return None
        # 新增文件後清除快取，確保後續搜尋能看到新資料
        self.invalidate_cache()
        return doc_id

    @staticmethod
    def make_deterministic_id(file_stem: str, collection_name: str = "examples") -> str:
        """依據檔名 stem + 集合名稱產生穩定的 doc ID（24 hex chars）。

        同一檔案不論執行幾次 sync/ingest，都會得到相同 ID，
        使 ChromaDB upsert 能正確覆寫而不新增重複文件。
        """
        raw = f"{collection_name}::{file_stem}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def document_exists(self, doc_id: str, collection_name: str = "examples") -> bool:
        """檢查指定 ID 的文件是否已存在於集合中。"""
        if not self._available:
            return False
        if collection_name == "regulations":
            target_collection = self.regulations_collection
        elif collection_name == "policies":
            target_collection = self.policies_collection
        else:
            target_collection = self.examples_collection
        try:
            with suppress_known_third_party_deprecations_temporarily():
                result = target_collection.get(ids=[doc_id], include=[])
            return len(result.get("ids", [])) > 0
        except _KB_MANAGER_VENDOR_EXCEPTIONS as exc:
            _log_kb_warning(f"查詢文件是否存在 collection={collection_name} doc_id={doc_id}", exc)
            return False

    def upsert_document(
        self,
        doc_id: str,
        content: str,
        metadata: dict[str, Any],
        collection_name: str = "examples",
        full_document: str | None = None,
        chunk_index: int | None = None,
        total_chunks: int | None = None,
    ) -> str | None:
        """以確定性 ID upsert 文件——冪等操作，可安全重複呼叫。

        與 add_document 的差異：
        - 使用呼叫方提供的 doc_id（應為 make_deterministic_id() 的輸出）
        - 呼叫 ChromaDB upsert() 而非 add()，相同 ID 時更新而不重複寫入
        """
        if not self._available:
            logger.warning("知識庫不可用，無法 upsert 文件。")
            return None
        if not content or not content.strip():
            logger.warning("無法 upsert 空白內容的文件")
            return None

        if self.contextual_retrieval and full_document:
            idx = chunk_index if chunk_index is not None else 0
            total = total_chunks if total_chunks is not None else 1
            content = self._enrich_with_context(content, full_document, idx, total)

        embedding = self.llm_provider.embed(content)
        if not embedding:
            logger.warning("無法產生文件的嵌入向量: %s", metadata.get("title", "未知"))
            return None

        if collection_name == "regulations":
            target_collection = self.regulations_collection
        elif collection_name == "policies":
            target_collection = self.policies_collection
        else:
            target_collection = self.examples_collection

        try:
            with suppress_known_third_party_deprecations_temporarily():
                target_collection.upsert(
                    documents=[content],
                    embeddings=[embedding],
                    metadatas=[metadata],
                    ids=[doc_id],
                )
        except _KB_MANAGER_VENDOR_EXCEPTIONS as e:
            logger.error("文件 upsert 知識庫失敗: %s", e)
            return None
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
        except _KB_MANAGER_VENDOR_EXCEPTIONS as e:
            _log_kb_warning("Contextual enrichment", e)
        return chunk

    @property
    def is_available(self) -> bool:
        """知識庫是否可用。"""
        return self._available

    def invalidate_cache(self) -> None:
        """清除所有快取。在 ingest / reset 後呼叫以確保資料一致性。"""
        with self._cache_lock:
            self._search_cache.clear()
        with self._embed_cache_lock:
            self._embed_cache.clear()
        with self._doc_cache_lock:
            self._doc_cache.clear()
        logger.debug("搜尋快取、embedding 快取和文件集合快取已清除")
