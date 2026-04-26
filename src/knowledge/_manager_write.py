import hashlib
import logging
from typing import Any
import uuid

import src.core.warnings_compat as warnings_compat


logger = logging.getLogger(__name__)

suppress_known_third_party_deprecations_temporarily = getattr(
    warnings_compat,
    "suppress_known_third_party_deprecations_temporarily",
    warnings_compat.suppress_known_third_party_deprecations,
)

_KB_WRITE_VENDOR_EXCEPTIONS = (Exception,)


def _log_kb_warning(action: str, exc: Exception) -> None:
    """記錄可預期的知識庫降級錯誤。"""
    logger.warning("%s 失敗: %s", action, exc)


class KnowledgeWriteMixin:
    @staticmethod
    def make_deterministic_id(file_stem: str, collection_name: str = "examples") -> str:
        """依據檔名 stem + 集合名稱產生穩定的 doc ID（24 hex chars）。"""
        raw = f"{collection_name}::{file_stem}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def _write_collection(self, collection_name: str) -> Any:
        if collection_name == "regulations":
            return self.regulations_collection
        if collection_name == "policies":
            return self.policies_collection
        return self.examples_collection

    def _prepare_document_content(
        self,
        content: str,
        full_document: str | None,
        chunk_index: int | None,
        total_chunks: int | None,
    ) -> str:
        if self.contextual_retrieval and full_document:
            idx = chunk_index if chunk_index is not None else 0
            total = total_chunks if total_chunks is not None else 1
            return self._enrich_with_context(content, full_document, idx, total)
        return content

    def document_exists(self, doc_id: str, collection_name: str = "examples") -> bool:
        """檢查指定 ID 的文件是否已存在於集合中。"""
        if not self._available:
            return False
        target_collection = self._write_collection(collection_name)
        try:
            with suppress_known_third_party_deprecations_temporarily():
                result = target_collection.get(ids=[doc_id], include=[])
            return len(result.get("ids", [])) > 0
        except _KB_WRITE_VENDOR_EXCEPTIONS as exc:
            _log_kb_warning(f"查詢文件是否存在 collection={collection_name} doc_id={doc_id}", exc)
            return False

    def add_document(
        self,
        content: str,
        metadata: dict[str, Any],
        collection_name: str = "examples",
        full_document: str | None = None,
        chunk_index: int | None = None,
        total_chunks: int | None = None,
    ) -> str | None:
        """新增文件到知識庫，必要時先套用 Contextual Retrieval。"""
        if not self._available:
            logger.warning("知識庫不可用，無法新增文件。")
            return None
        if not content or not content.strip():
            logger.warning("無法新增空白內容的文件")
            return None

        content = self._prepare_document_content(
            content, full_document, chunk_index, total_chunks
        )
        doc_id = str(uuid.uuid4())
        embedding = self.llm_provider.embed(content)
        if not embedding:
            logger.warning("無法產生文件的嵌入向量: %s", metadata.get("title", "未知"))
            return None

        try:
            with suppress_known_third_party_deprecations_temporarily():
                self._write_collection(collection_name).add(
                    documents=[content],
                    embeddings=[embedding],
                    metadatas=[metadata],
                    ids=[doc_id],
                )
        except _KB_WRITE_VENDOR_EXCEPTIONS as exc:
            logger.error("文件寫入知識庫失敗: %s", exc)
            return None
        self.invalidate_cache()
        return doc_id

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
        """以確定性 ID upsert 文件——冪等操作，可安全重複呼叫。"""
        if not self._available:
            logger.warning("知識庫不可用，無法 upsert 文件。")
            return None
        if not content or not content.strip():
            logger.warning("無法 upsert 空白內容的文件")
            return None

        content = self._prepare_document_content(
            content, full_document, chunk_index, total_chunks
        )
        embedding = self.llm_provider.embed(content)
        if not embedding:
            logger.warning("無法產生文件的嵌入向量: %s", metadata.get("title", "未知"))
            return None

        try:
            with suppress_known_third_party_deprecations_temporarily():
                self._write_collection(collection_name).upsert(
                    documents=[content],
                    embeddings=[embedding],
                    metadatas=[metadata],
                    ids=[doc_id],
                )
        except _KB_WRITE_VENDOR_EXCEPTIONS as exc:
            logger.error("文件 upsert 知識庫失敗: %s", exc)
            return None
        self.invalidate_cache()
        return doc_id
