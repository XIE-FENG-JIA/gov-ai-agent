import logging
import chromadb
from typing import List, Dict, Optional, Any
import uuid
from src.core.llm import LLMProvider

logger = logging.getLogger(__name__)

class KnowledgeBaseManager:
    """管理本地 ChromaDB 知識庫。"""

    def __init__(self, persist_path: str, llm_provider: LLMProvider):
        self.persist_path = persist_path
        self.llm_provider = llm_provider
        self._available = True

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

    def add_document(self, content: str, metadata: Dict[str, Any], collection_name: str = "examples") -> Optional[str]:
        """將文件新增至指定的集合。"""
        if not self._available:
            logger.warning("知識庫不可用，無法新增文件。")
            return None

        # 防護空值內容
        if not content or not content.strip():
            logger.warning("無法新增空白內容的文件")
            return None

        doc_id = str(uuid.uuid4())

        # Generate embedding using our LLM provider
        embedding = self.llm_provider.embed(content)

        if not embedding:
            logger.warning("Failed to generate embedding for doc: %s", metadata.get('title', 'unknown'))
            return None

        if collection_name == "regulations":
            target_collection = self.regulations_collection
        elif collection_name == "policies":
            target_collection = self.policies_collection
        else:
            target_collection = self.examples_collection
        
        target_collection.add(
            documents=[content],
            embeddings=[embedding],
            metadatas=[metadata],
            ids=[doc_id]
        )
        return doc_id

    def search_policies(self, query: str, n_results: int = 3) -> List[Dict]:
        """在政策集合中搜尋。"""
        if not self._available:
            return []
        query_embedding = self.llm_provider.embed(query)
        if not query_embedding:
            logger.warning("Empty embedding for policy search query, skipping.")
            return []

        if self.policies_collection.count() == 0:
            return []

        results = self.policies_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        
        formatted = []
        if results['ids']:
            for i in range(len(results['ids'][0])):
                formatted.append({
                    "content": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i] if results['distances'] else None
                })
        return formatted

    def search_examples(self, query: str, n_results: int = 3, filter_metadata: Optional[Dict] = None) -> List[Dict]:
        """搜尋相似的範例文件。"""
        if not self._available:
            return []
        query_embedding = self.llm_provider.embed(query)

        if not query_embedding:
            logger.warning("Empty embedding for example search query, skipping.")
            return []

        if self.examples_collection.count() == 0:
            return []

        results = self.examples_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_metadata
        )
        
        # Format results
        formatted_results = []
        if results['ids']:
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    "id": results['ids'][0][i],
                    "content": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i] if results['distances'] else None
                })
        
        return formatted_results

    def search_regulations(self, query: str, doc_type: Optional[str] = None, n_results: int = 3) -> List[Dict]:
        """在法規集合中搜尋，可依公文類型篩選。"""
        if not self._available:
            return []
        query_embedding = self.llm_provider.embed(query)
        if not query_embedding:
            logger.warning("Empty embedding for regulation search query, skipping.")
            return []

        if self.regulations_collection.count() == 0:
            return []

        where_filter = {"doc_type": doc_type} if doc_type else None

        results = self.regulations_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter
        )
        
        formatted = []
        if results['ids']:
            for i in range(len(results['ids'][0])):
                formatted.append({
                    "content": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i] if results['distances'] else None
                })
        return formatted

    def get_stats(self) -> Dict[str, int]:
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
        """危險操作：重設資料庫（刪除所有集合後重建）。"""
        if not self._available:
            logger.warning("知識庫不可用，無法重設。")
            return
        collection_names = ["public_doc_examples", "regulations", "policies"]
        for name in collection_names:
            try:
                self.client.delete_collection(name)
            except Exception:
                logger.debug("集合 %s 不存在，跳過刪除", name)
        # 重建集合
        self.examples_collection = self.client.get_or_create_collection(
            name="public_doc_examples", metadata={"hnsw:space": "cosine"}
        )
        self.regulations_collection = self.client.get_or_create_collection(
            name="regulations", metadata={"hnsw:space": "cosine"}
        )
        self.policies_collection = self.client.get_or_create_collection(
            name="policies", metadata={"hnsw:space": "cosine"}
        )

    def add_example(self, content: str, metadata: Dict[str, Any]) -> Optional[str]:
        """相容性包裝函式，呼叫 add_document。"""
        return self.add_document(content, metadata, "examples")
