"""FastAPI app factory and startup helpers."""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import src.api.dependencies as _deps
import src.api.middleware as _mw
from src.api.dependencies import get_config, get_kb, get_llm
from src.api.middleware import RequestBodyLimitMiddleware, security_middleware
from src.api.routes import agents, engines, health, knowledge, workflow
from src.api._startup import _cleanup_old_outputs, _preflight_check, _warmup_law_cache
from src.core.constants import API_VERSION
from src.core.logging_config import setup_logging as _shared_setup_logging

logger = logging.getLogger(__name__)


def _expand_loopback_origins(origins: list[str]) -> list[str]:
    """Expand localhost origins to IPv4/IPv6 loopback variants."""
    expanded: list[str] = []
    seen: set[str] = set()

    for origin in origins:
        value = origin.strip()
        if not value or value in seen:
            continue

        seen.add(value)
        expanded.append(value)

        parsed = urlsplit(value)
        if parsed.hostname != "localhost":
            continue

        for loopback_host in ("127.0.0.1", "[::1]"):
            netloc = loopback_host
            if parsed.port is not None:
                netloc = f"{loopback_host}:{parsed.port}"
            variant = urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))
            if variant not in seen:
                seen.add(variant)
                expanded.append(variant)

    return expanded


_ALLOWED_ORIGINS = _expand_loopback_origins([
    origin.strip()
    for origin in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5678,http://127.0.0.1:5678,"
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:8080,http://127.0.0.1:8080",
    ).split(",")
    if origin.strip()
])

_ALLOWED_HEADERS: list[str] = [
    "Content-Type",
    "Accept",
    "Authorization",
    "X-API-Key",
    "X-Request-ID",
]


def _setup_logging() -> None:
    """Configure production logging."""
    _shared_setup_logging(force=True, suppress_noisy=True)


def _ensure_api_key() -> None:
    """Ensure API keys exist before the web UI starts calling API routes."""
    _mw.ensure_api_key(get_config())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize shared resources on startup and clean them up on shutdown."""
    _setup_logging()
    logger.info("正在初始化 API 資源...")
    _cleanup_old_outputs()
    _preflight_check()
    if _deps.executor._shutdown:
        from src.core.constants import API_MAX_WORKERS as _amw

        _deps.executor = ThreadPoolExecutor(max_workers=_amw)
    get_config()
    _ensure_api_key()
    get_llm()
    get_kb()
    threading.Thread(target=_warmup_law_cache, daemon=True).start()
    logger.info("API 資源就緒。")
    yield
    logger.info("正在關閉 API，等待進行中的任務完成...")
    _deps.executor.shutdown(wait=True, cancel_futures=True)
    logger.info("API 已關閉。")


def _build_app_kwargs() -> dict[str, object]:
    docs_enabled = os.environ.get("ENABLE_API_DOCS", "true").lower() == "true"
    return {
        "title": "公文 AI Agent API",
        "description": (
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
        "version": API_VERSION,
        "docs_url": "/docs" if docs_enabled else None,
        "redoc_url": "/redoc" if docs_enabled else None,
        "lifespan": lifespan,
        "openapi_tags": [
            {"name": "健康檢查", "description": "伺服器狀態與健康檢查端點"},
            {"name": "需求分析", "description": "將自然語言轉換為結構化公文需求"},
            {"name": "草稿撰寫", "description": "根據結構化需求撰寫公文草稿"},
            {"name": "審查", "description": "各類審查 Agent（格式、文風、事實、一致性、合規）"},
            {"name": "修改", "description": "依審查意見修正草稿"},
            {"name": "完整流程", "description": "一鍵完成需求分析→撰寫→審查→修改→輸出"},
        ],
    }


def _configure_cors(app: FastAPI) -> None:
    credentials_enabled = os.environ.get("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"
    if credentials_enabled and "*" in _ALLOWED_ORIGINS:
        logger.warning(
            "SECURITY: allow_credentials=True 不可與 '*' origins 搭配使用。已自動將 allow_credentials 設為 False。"
        )
        credentials_enabled = False
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_ALLOWED_ORIGINS,
        allow_credentials=credentials_enabled,
        allow_methods=["GET", "POST"],
        allow_headers=_ALLOWED_HEADERS,
    )


def _mount_web_ui(app: FastAPI) -> None:
    try:
        from src.web_preview.app import web_app as _web_app

        app.mount("/ui", _web_app)
        logger.info("Web UI 已掛載於 /ui")
    except ImportError:
        logger.warning("Web UI 模組未安裝，跳過掛載。")

    # gov-ai/static — 引擎切換器 + mockup（顶层設計：UI 與 backend 拉通）
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse, RedirectResponse

    static_dir = Path(__file__).resolve().parents[2] / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        logger.info("Static 目錄掛載於 /static (%s)", static_dir)

        @app.get("/engine", include_in_schema=False)
        async def _engine_switcher() -> FileResponse:
            return FileResponse(str(static_dir / "engine-switcher.html"))

        mockup = static_dir / "gov-ai-mockup-v1.html"
        if not mockup.exists():
            alt = Path(__file__).resolve().parents[2] / "gov-ai-mockup-v1.html"
            if alt.exists():
                mockup = alt

        if mockup.exists():
            @app.get("/mockup", include_in_schema=False)
            async def _mockup() -> FileResponse:
                return FileResponse(str(mockup))
            logger.info("Mockup 掛載於 /mockup (%s)", mockup)


def _configure_middleware(app: FastAPI) -> None:
    app.middleware("http")(security_middleware)
    app.add_middleware(RequestBodyLimitMiddleware)


def _include_routers(app: FastAPI) -> None:
    app.include_router(health.router)
    app.include_router(agents.router)
    app.include_router(workflow.router)
    app.include_router(knowledge.router)
    app.include_router(engines.router)


def create_app() -> FastAPI:
    """Build a fully configured FastAPI app instance."""
    app = FastAPI(**_build_app_kwargs())
    _configure_cors(app)
    _mount_web_ui(app)
    _configure_middleware(app)
    _include_routers(app)
    return app


def resolve_bind_host(
    host: str,
    auth_enabled: bool,
    api_keys: list[str],
    *,
    allow_insecure_bind: bool = False,
) -> str:
    """Return a safe bind host for the current auth configuration."""
    if host == "127.0.0.1":
        return host

    if auth_enabled and not api_keys:
        logger.warning(
            "SECURITY: API 認證已啟用但未設定任何 api_keys，"
            "強制將綁定地址從 %s 改為 127.0.0.1 以防止外部存取。"
            "請在 config.yaml 的 api.api_keys 中設定至少一組 key 後再開放外部連線。",
            host,
        )
        return "127.0.0.1"

    if not auth_enabled:
        if allow_insecure_bind:
            logger.warning(
                "SECURITY: API 認證已停用且綁定地址為 %s，"
                "已透過 ALLOW_INSECURE_BIND=true 明確允許。"
                "所有端點將對外暴露且無需認證——請確保網路層有其他防護。",
                host,
            )
            return host

        logger.warning(
            "SECURITY: API 認證已停用 (auth_enabled=false) 且綁定地址為 %s，"
            "強制將綁定地址改為 127.0.0.1 以防止未認證的外部存取。"
            "如需對外開放無認證服務，請設定環境變數 ALLOW_INSECURE_BIND=true。",
            host,
        )
        return "127.0.0.1"

    return host
