#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FastAPI Server for Gov AI Agent - n8n Integration
=================================================

啟動方式：
    uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload

n8n 呼叫方式：
    HTTP Request Node -> http://localhost:8000/api/v1/{endpoint}

模組結構：
    src/api/models.py        — Pydantic Request/Response 模型
    src/api/middleware.py     — 限流、指標收集、安全標頭、認證
    src/api/helpers.py        — 工具函式（錯誤處理、非同步執行器）
    src/api/dependencies.py   — 全域共享實例（config, LLM, KB）
    src/api/routes/health.py  — 健康檢查與效能監控
    src/api/routes/agents.py  — Agent 路由（需求、撰寫、審查、修改）
    src/api/routes/workflow.py — 完整流程、批次處理、檔案下載
    src/api/routes/knowledge.py — 知識庫搜尋
"""

import logging
import os
import sys
import threading
import types
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.constants import API_VERSION
from src.core.logging_config import setup_logging as _shared_setup_logging

import src.api.dependencies as _deps
import src.api.middleware as _mw

from src.api.dependencies import get_config, get_llm, get_kb, get_org_memory, executor
from src.api.middleware import security_middleware

# 路由模組
from src.api.routes import health, agents, workflow, knowledge

# ============================================================
# 向後相容 re-export（讓 `from api_server import X` 繼續可用）
# ============================================================
from src.api.models import (  # noqa: F401
    _VALID_AGENT_NAMES,
    RequirementRequest, RequirementResponse,
    WriterRequest, WriterResponse,
    ReviewRequest, ReviewResponse, SingleAgentReviewResponse,
    MeetingRequest, MeetingResponse,
    ParallelReviewRequest, ParallelReviewResponse,
    RefineRequest, RefineResponse,
    BatchRequest, BatchItemResult, BatchResponse,
    KBSearchRequest, KBSearchResponse,
)
from src.api.helpers import (  # noqa: F401
    _TRUST_PROXY, _get_client_ip,
    _sanitize_error, _get_error_code,
    review_result_to_dict, _sanitize_output_filename,
    run_in_executor as _run_in_executor,
    ENDPOINT_TIMEOUT as _ENDPOINT_TIMEOUT,
    MEETING_TIMEOUT as _MEETING_TIMEOUT,
)
from src.api.middleware import (  # noqa: F401
    _RateLimiter, _MetricsCollector, _RATE_LIMIT_RPM,
)
# Agent / 元件 re-export（測試中 patch("api_server.X") 需要這些名稱）
from src.core.config import ConfigManager  # noqa: F401
from src.core.llm import get_llm_factory  # noqa: F401
from src.knowledge.manager import KnowledgeBaseManager  # noqa: F401
from src.agents.requirement import RequirementAgent  # noqa: F401
from src.agents.writer import WriterAgent  # noqa: F401
from src.agents.template import TemplateEngine  # noqa: F401
from src.agents.style_checker import StyleChecker  # noqa: F401
from src.agents.fact_checker import FactChecker  # noqa: F401
from src.agents.consistency_checker import ConsistencyChecker  # noqa: F401
from src.agents.compliance_checker import ComplianceChecker  # noqa: F401
from src.agents.auditor import FormatAuditor  # noqa: F401
from src.agents.review_parser import format_audit_to_review_result  # noqa: F401
from src.document.exporter import DocxExporter  # noqa: F401
from fastapi.responses import FileResponse  # noqa: F401
# 路由處理器函式 re-export
from src.api.routes.agents import (  # noqa: F401
    refine_draft, parallel_review, _run_format_audit,
    analyze_requirement, write_draft,
    review_format, review_style, review_fact,
    review_consistency, review_compliance,
)
from src.api.routes.workflow import (  # noqa: F401
    run_meeting, download_file, run_batch,
    _execute_document_workflow,
)
from src.api.routes.knowledge import kb_search  # noqa: F401
from src.api.routes.health import health_check, get_metrics  # noqa: F401

logger = logging.getLogger(__name__)


# ============================================================
# CORS 允許來源設定（安全性：避免使用萬用字元 "*"）
# ============================================================
_ALLOWED_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5678,http://localhost:3000,http://localhost:8080",
    ).split(",")
    if origin.strip()
]

# 僅允許 API 實際需要的 HTTP 標頭（避免使用萬用字元 "*"）
_ALLOWED_HEADERS: list[str] = [
    "Content-Type",
    "Accept",
    "Authorization",
    "X-API-Key",
    "X-Request-ID",
]


# ============================================================
# Lifespan
# ============================================================

def _setup_logging() -> None:
    """配置生產環境日誌格式（委託至 src.core.logging_config）。"""
    _shared_setup_logging(force=True, suppress_noisy=True)


def _preflight_check() -> None:
    """啟動前環境檢查：驗證必要環境變數與配置。

    檢查失敗時記錄 WARNING 但不阻止啟動，
    讓服務至少能回應 health check 以便診斷問題。
    """
    config = get_config()
    llm_config = config.get("llm", {})

    provider = llm_config.get("provider", "ollama")
    api_key = llm_config.get("api_key", "")

    # 雲端 provider 需要 API key
    cloud_providers = {"openrouter", "gemini", "openai", "anthropic"}
    if provider in cloud_providers and not api_key:
        logger.warning(
            "PREFLIGHT: LLM provider=%s 需要 API key，但 LLM_API_KEY 未設定。"
            " LLM 呼叫將會失敗。請在 .env 或環境變數中設定 LLM_API_KEY。",
            provider,
        )

    model = llm_config.get("model", "")
    if not model:
        logger.warning("PREFLIGHT: LLM model 未設定，將使用預設值。")

    kb_path = config.get("knowledge_base", {}).get("path", "./kb_data")
    if not Path(kb_path).exists():
        logger.warning(
            "PREFLIGHT: 知識庫路徑 '%s' 不存在，KB 將在首次使用時建立。",
            kb_path,
        )

    # 多 worker 限流警告
    from src.api.middleware import _RATE_LIMIT_RPM
    workers = int(os.environ.get("API_WORKERS", "1"))
    if workers > 1:
        logger.warning(
            "PREFLIGHT: API_WORKERS=%d > 1，in-process 速率限制器在多進程模式下"
            "每個 worker 獨立計數，實際限流為 %d × %d = %d RPM。"
            "生產環境建議使用 Redis 實現跨進程速率限制。",
            workers, workers, _RATE_LIMIT_RPM, workers * _RATE_LIMIT_RPM,
        )

    # API 認證檢查
    api_config = config.get("api", {})
    auth_enabled = api_config.get("auth_enabled", True)
    api_keys = api_config.get("api_keys", [])

    if not auth_enabled:
        logger.warning(
            "PREFLIGHT: API 認證已停用 (auth_enabled=false)，"
            "所有端點將無需認證即可存取。生產環境請務必啟用認證。"
        )
    elif not api_keys:
        logger.critical(
            "PREFLIGHT: API 認證已啟用但 api_keys 為空，"
            "所有受保護端點將回傳 401。"
            "請在 config.yaml 的 api.api_keys 中設定至少一組 key。"
        )

    logger.info(
        "PREFLIGHT: provider=%s, model=%s, has_api_key=%s, kb_path=%s, "
        "auth_enabled=%s, api_keys_count=%d",
        provider, model, bool(api_key), kb_path,
        auth_enabled, len(api_keys),
    )


def _ensure_api_key() -> None:
    """啟動時檢查 api_keys，若為空則提前生成，避免 Web UI 呼叫 API 時 401。"""
    _mw.ensure_api_key(get_config())


def _warmup_law_cache() -> None:
    """背景預熱法規快取，避免首次請求時阻塞 worker 執行緒 ~120s。"""
    try:
        from src.knowledge.realtime_lookup import LawVerifier
        verifier = LawVerifier()
        verifier._ensure_cache()
        logger.info("法規快取預熱完成。")
    except Exception:
        logger.warning("法規快取預熱失敗，將於首次使用時重試。", exc_info=True)


def _cleanup_old_outputs() -> None:
    """掃描 output/ 目錄，刪除超過 24 小時的 .docx 檔案。"""
    import pathlib
    import time as _time

    output_dir = pathlib.Path("output")
    if not output_dir.exists():
        return
    cutoff = _time.time() - 86400  # 24 hours
    count = 0
    for f in output_dir.glob("*.docx"):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            count += 1
    if count:
        logger.info("清理 %d 個超過 24 小時的輸出檔案", count)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """在啟動時初始化共享資源，關閉時清理。"""
    _setup_logging()
    logger.info("正在初始化 API 資源...")
    _cleanup_old_outputs()
    _preflight_check()
    get_config()
    _ensure_api_key()
    get_llm()
    get_kb()
    # 背景預熱法規快取（不阻塞啟動）
    threading.Thread(target=_warmup_law_cache, daemon=True).start()
    logger.info("API 資源就緒。")
    yield
    logger.info("正在關閉 API，等待進行中的任務完成...")
    executor.shutdown(wait=True, cancel_futures=True)
    logger.info("API 已關閉。")


# ============================================================
# App 建立與組裝
# ============================================================

app = FastAPI(
    title="公文 AI Agent API",
    description=(
        "n8n 整合用的公文 AI Agent REST API。\n\n"
        "提供公文需求分析、草稿撰寫、多 Agent 審查、自動修正等功能。\n\n"
        "## 端點分類\n"
        "- **健康檢查**: 伺服器狀態查詢\n"
        "- **需求分析**: 自然語言轉結構化需求\n"
        "- **草稿撰寫**: 依需求產生公文草稿\n"
        "- **審查**: 格式、文風、事實、一致性、合規性審查\n"
        "- **修改**: 依審查意見修正草稿\n"
        "- **完整流程**: 一鍵完成需求→撰寫→審查→修改→輸出"
    ),
    version=API_VERSION,
    docs_url="/docs" if os.environ.get("ENABLE_API_DOCS", "true").lower() == "true" else None,
    redoc_url="/redoc" if os.environ.get("ENABLE_API_DOCS", "true").lower() == "true" else None,
    lifespan=lifespan,
    openapi_tags=[
        {"name": "健康檢查", "description": "伺服器狀態與健康檢查端點"},
        {"name": "需求分析", "description": "將自然語言轉換為結構化公文需求"},
        {"name": "草稿撰寫", "description": "根據結構化需求撰寫公文草稿"},
        {"name": "審查", "description": "各類審查 Agent（格式、文風、事實、一致性、合規）"},
        {"name": "修改", "description": "依審查意見修正草稿"},
        {"name": "完整流程", "description": "一鍵完成需求分析→撰寫→審查→修改→輸出"},
    ],
)

# CORS 設定（使用環境變數控制允許來源，標頭限定為實際需要的項目）
# 安全性：n8n 整合通常不需要瀏覽器 Cookie，預設關閉 credentials
_CORS_CREDENTIALS = os.environ.get("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"
if _CORS_CREDENTIALS and "*" in _ALLOWED_ORIGINS:
    logger.warning(
        "SECURITY: allow_credentials=True 不可與 '*' origins 搭配使用。"
        "已自動將 allow_credentials 設為 False。"
    )
    _CORS_CREDENTIALS = False
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=_CORS_CREDENTIALS,
    allow_methods=["GET", "POST"],
    allow_headers=_ALLOWED_HEADERS,
)


# ============================================================
# Web UI（掛載在 /ui）
# ============================================================

try:
    from src.web_preview.app import web_app as _web_app
    app.mount("/ui", _web_app)
    logger.info("Web UI 已掛載於 /ui")
except ImportError:
    logger.warning("Web UI 模組未安裝，跳過掛載。")


# ============================================================
# 中介層
# ============================================================

app.middleware("http")(security_middleware)


# ============================================================
# 路由掛載
# ============================================================

app.include_router(health.router)
app.include_router(agents.router)
app.include_router(workflow.router)
app.include_router(knowledge.router)


# ============================================================
# Main
# ============================================================

# ============================================================
# 向後相容：模組級狀態代理
# ============================================================
# 測試中 `api_server._config = None` 直接操作全域狀態，
# 需要代理到 src.api.dependencies / src.api.middleware。


class _BackwardCompatModule(types.ModuleType):
    """包裝原始模組，讓全域狀態讀寫能透明代理到子模組。

    過渡方案：供舊測試直接 patch api_server._config 等全域狀態用。
    長期應更新測試改為 import src.api.dependencies，屆時可移除此類別。
    """

    # 需要代理到 dependencies 的狀態屬性
    _DEPS_ATTRS = frozenset({"_config", "_llm", "_kb", "_org_memory", "_init_lock"})
    # 別名映射到 dependencies
    _DEPS_ALIAS_MAP = {"_executor": "executor"}
    # 需要代理到 middleware 的狀態屬性
    _MW_ATTR_MAP = {
        "_rate_limiter": "rate_limiter",
        "_metrics": "metrics",
    }

    def __init__(self, orig_module):
        # 複製原始模組的所有屬性
        super().__init__(orig_module.__name__)
        self.__dict__.update(orig_module.__dict__)
        self._orig_module = orig_module

    def __getattr__(self, name):
        if name in self._DEPS_ATTRS:
            return getattr(_deps, name)
        if name in self._DEPS_ALIAS_MAP:
            return getattr(_deps, self._DEPS_ALIAS_MAP[name])
        if name in self._MW_ATTR_MAP:
            return getattr(_mw, self._MW_ATTR_MAP[name])
        raise AttributeError(f"module 'api_server' has no attribute {name!r}")

    def __setattr__(self, name, value):
        if name in ("_orig_module",) or name.startswith("__"):
            super().__setattr__(name, value)
        elif name in self._DEPS_ATTRS:
            setattr(_deps, name, value)
        elif name in self._DEPS_ALIAS_MAP:
            setattr(_deps, self._DEPS_ALIAS_MAP[name], value)
        elif name in self._MW_ATTR_MAP:
            setattr(_mw, self._MW_ATTR_MAP[name], value)
        else:
            super().__setattr__(name, value)


# 替換模組為代理版本
sys.modules[__name__] = _BackwardCompatModule(sys.modules[__name__])


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    import uvicorn

    _host = os.environ.get("API_HOST", "0.0.0.0")
    _port = int(os.environ.get("API_PORT", "8000"))
    _workers = int(os.environ.get("API_WORKERS", "1"))
    _log_level = os.environ.get("LOG_LEVEL", "info").lower()

    # 安全檢查：無 API key 時強制限制為 localhost
    _startup_config = get_config()
    _startup_api = _startup_config.get("api", {})
    _startup_auth = _startup_api.get("auth_enabled", True)
    _startup_keys = _startup_api.get("api_keys", [])

    if _startup_auth and not _startup_keys and _host != "127.0.0.1":
        logger.warning(
            "SECURITY: API 認證已啟用但未設定任何 api_keys，"
            "強制將綁定地址從 %s 改為 127.0.0.1 以防止外部存取。"
            "請在 config.yaml 的 api.api_keys 中設定至少一組 key 後再開放外部連線。",
            _host,
        )
        _host = "127.0.0.1"

    if not _startup_auth and _host != "127.0.0.1":
        logger.warning(
            "SECURITY: API 認證已停用 (auth_enabled=false) 且綁定地址為 %s，"
            "所有端點將對外暴露且無需認證。生產環境請務必啟用認證。",
            _host,
        )

    uvicorn.run(
        "api_server:app",
        host=_host,
        port=_port,
        workers=_workers,
        log_level=_log_level,
    )
