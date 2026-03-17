"""
全域依賴注入 — 共享實例的延遲初始化與存取
===========================================

所有需要共享的全域物件（config, LLM, KB, OrgMemory, executor）集中管理。
路由模組透過本模組取得這些物件。
"""

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from src.core.config import ConfigManager
from src.core.llm import get_llm_factory
from src.core.constants import API_MAX_WORKERS
from src.knowledge.manager import KnowledgeBaseManager
from src.agents.org_memory import OrganizationalMemory

logger = logging.getLogger(__name__)

# 全域實例（在 lifespan 中初始化，使用雙重檢查鎖確保執行緒安全）
_config: dict[str, Any] | None = None
_llm: Any | None = None
_kb: KnowledgeBaseManager | None = None
_org_memory: OrganizationalMemory | None = None
_init_lock = threading.RLock()  # 可重入鎖：get_llm → get_config 巢狀取鎖
executor = ThreadPoolExecutor(max_workers=API_MAX_WORKERS)


def get_config() -> dict[str, Any]:
    """取得全域設定，延遲初始化（執行緒安全，使用雙重檢查鎖）。"""
    global _config
    if _config is not None:
        return _config
    with _init_lock:
        if _config is None:
            try:
                _config = ConfigManager().config
            except Exception as e:
                logger.exception("設定檔載入失敗，使用預設設定: %s", e)
                _config = {
                    "llm": {"provider": "ollama", "model": "mistral"},
                    "knowledge_base": {"path": "./kb_data"},
                }
    return _config


def get_llm():
    """取得 LLM provider 實例，延遲初始化（執行緒安全）。"""
    global _llm
    if _llm is not None:
        return _llm
    with _init_lock:
        if _llm is None:
            config = get_config()
            llm_config = config.get("llm", {"provider": "ollama", "model": "mistral"})
            _llm = get_llm_factory(llm_config, full_config=config)
    return _llm


def get_kb() -> KnowledgeBaseManager:
    """取得知識庫管理器實例，延遲初始化（執行緒安全，不可用時回傳降級實例）。"""
    global _kb
    if _kb is not None:
        return _kb
    with _init_lock:
        if _kb is None:
            kb_path = get_config().get("knowledge_base", {}).get("path", "./kb_data")
            _kb = KnowledgeBaseManager(kb_path, get_llm())
    return _kb


def get_org_memory() -> OrganizationalMemory | None:
    """取得機構記憶實例，延遲初始化（執行緒安全）。若停用則回傳 None。"""
    global _org_memory
    if _org_memory is not None:
        return _org_memory
    with _init_lock:
        if _org_memory is None:
            config = get_config()
            om_config = config.get("organizational_memory", {})
            if om_config.get("enabled", False):
                storage_path = om_config.get(
                    "storage_path", "./kb_data/agency_preferences.json"
                )
                _org_memory = OrganizationalMemory(storage_path=storage_path)
    return _org_memory


def get_raw_kb() -> KnowledgeBaseManager | None:
    """直接取得 _kb 實例（不觸發初始化），用於 health check。"""
    return _kb


def get_raw_llm():
    """直接取得 _llm 實例（不觸發初始化），用於 health check。"""
    return _llm
