# -*- coding: utf-8 -*-
"""
Web UI 預覽 — FastAPI + Jinja2 + HTMX
======================================

掛載在主 API 的 /ui 路徑下，透過呼叫 API 端點實現功能，
避免重複初始化 agents。
"""

import json
import logging
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.core.constants import MAX_USER_INPUT_LENGTH
from src.core.models import VALID_DOC_TYPES
from src.api.dependencies import get_config
from src.cli.utils import detect_state_dir, resolve_state_read_path

logger = logging.getLogger(__name__)
_WEB_UI_EXCEPTIONS = (
    httpx.HTTPError,
    json.JSONDecodeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)

_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _DIR.parent.parent
_WEB_UI_STATE_DIR = detect_state_dir(str(_PROJECT_ROOT))

web_app = FastAPI(docs_url=None, redoc_url=None)

# 靜態檔案與模板
web_app.mount("/static", StaticFiles(directory=str(_DIR / "static")), name="web_static")
templates = Jinja2Templates(directory=str(_DIR / "templates"))
templates.env.autoescape = True

# 後端 API 基底 URL（透過環境變數可覆蓋）
_API_BASE = os.environ.get("WEB_UI_API_BASE", "http://127.0.0.1:8000")


def _parse_env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        return int(raw)
    except ValueError:
        logger.warning("環境變數 %s=%r 不是整數，改用預設值 %d", name, raw, default)
        return default


def _parse_env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, str(default))
    try:
        return float(raw)
    except ValueError:
        logger.warning("環境變數 %s=%r 不是數值，改用預設值 %.2f", name, raw, default)
        return default


_WEB_UI_RALPH_MAX_CYCLES = max(1, _parse_env_int("WEB_UI_RALPH_MAX_CYCLES", 2))
_WEB_UI_RALPH_TARGET_SCORE = max(0.0, min(1.0, _parse_env_float("WEB_UI_RALPH_TARGET_SCORE", 1.0)))


def _api_headers() -> dict[str, str]:
    """取得呼叫內部 API 所需的認證標頭。"""
    config = get_config()
    api_keys = config.get("api", {}).get("api_keys", [])
    if api_keys:
        return {"Authorization": f"Bearer {api_keys[0]}"}
    return {}

# SSRF 防護：僅允許本機地址與安全協議
_parsed = urlparse(_API_BASE)
if _parsed.scheme not in ("http", "https"):
    raise ValueError(f"WEB_UI_API_BASE 只允許 http/https 協議，不允許: {_parsed.scheme}")
if _parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
    raise ValueError(f"WEB_UI_API_BASE 只允許本機地址，不允許: {_parsed.hostname}")


@web_app.exception_handler(StarletteHTTPException)
async def web_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Web UI 的 HTTP 錯誤頁面，避免使用者看到 JSON raw data。"""
    return templates.TemplateResponse(
        request,
        "error.html",
        {"status_code": exc.status_code, "detail": exc.detail or "頁面未找到"},
        status_code=exc.status_code,
    )


def _sanitize_web_error(exc: Exception) -> str:
    """將例外轉為使用者友善的錯誤訊息，避免洩漏內部資訊。"""
    _SAFE = {
        "ConnectError": "無法連線至後端 API，請確認伺服器已啟動。",
        "TimeoutException": "請求逾時，請稍後再試。",
        "HTTPStatusError": "後端 API 回傳錯誤，請稍後再試。",
    }
    return _SAFE.get(type(exc).__name__, "發生內部錯誤，請稍後再試或聯繫管理員。")


def _log_web_warning(action: str, exc: Exception) -> None:
    """記錄可預期的 Web UI 降級錯誤。"""
    logger.warning("%s 失敗: %s", action, exc)


# ── 首頁 ─────────────────────────────────────────────
@web_app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首頁：輸入需求表單"""
    return templates.TemplateResponse(request, "index.html")


# ── 生成公文 ──────────────────────────────────────────
@web_app.post("/generate", response_class=HTMLResponse)
async def generate(
    request: Request,
    user_input: str = Form(...),
    doc_type: str = Form(""),
    skip_review: bool = Form(False),
    ralph_loop: bool = Form(False),
):
    """呼叫 /api/v1/meeting 端點生成公文，回傳結果頁"""
    error = None
    result = None

    # 輸入長度驗證
    stripped = user_input.strip()
    if len(stripped) < 5:
        return templates.TemplateResponse(
            request, "generate.html",
            {"user_input": user_input, "result": None, "error": "需求描述至少需要 5 個字。"},
        )
    if len(stripped) > MAX_USER_INPUT_LENGTH:
        return templates.TemplateResponse(
            request, "generate.html",
            {"user_input": user_input, "result": None,
             "error": f"需求描述不可超過 {MAX_USER_INPUT_LENGTH} 字（目前 {len(stripped)} 字）。"},
        )

    # 若使用者指定了合法公文類型，附加到 user_input 提示中
    effective_input = stripped
    if doc_type and doc_type in VALID_DOC_TYPES:
        effective_input = f"[公文類型：{doc_type}] {stripped}"

    try:
        meeting_timeout = 600.0 if (not skip_review and ralph_loop) else 180.0
        async with httpx.AsyncClient(timeout=meeting_timeout) as client:
            meeting_payload = {
                "user_input": effective_input,
                "skip_review": skip_review,
                "output_docx": True,
            }
            if not skip_review:
                meeting_payload["ralph_loop"] = ralph_loop
                if ralph_loop:
                    meeting_payload.update({
                        "use_graph": False,
                        "max_rounds": 2,
                        "ralph_max_cycles": _WEB_UI_RALPH_MAX_CYCLES,
                        "ralph_target_score": _WEB_UI_RALPH_TARGET_SCORE,
                    })

            resp = await client.post(
                f"{_API_BASE}/api/v1/meeting",
                headers=_api_headers(),
                json=meeting_payload,
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("success"):
                result = data
            else:
                error = data.get("error") or data.get("detail") or f"HTTP {resp.status_code}"
    except _WEB_UI_EXCEPTIONS as e:
        _log_web_warning("生成公文", e)
        error = _sanitize_web_error(e)

    return templates.TemplateResponse(
        request,
        "generate.html",
        {
            "user_input": user_input,
            "result": result,
            "error": error,
        },
    )


# ── 知識庫 ────────────────────────────────────────────
@web_app.get("/kb", response_class=HTMLResponse)
async def kb_page(request: Request):
    """知識庫統計與搜尋"""
    stats = None
    error = None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{_API_BASE}/api/v1/health", headers=_api_headers())
            if resp.status_code == 200:
                data = resp.json()
                stats = {
                    "kb_status": data.get("kb_status", "unknown"),
                    "kb_collections": data.get("kb_collections", 0),
                    "llm_provider": data.get("llm_provider", "unknown"),
                    "llm_model": data.get("llm_model", "unknown"),
                }
    except _WEB_UI_EXCEPTIONS as e:
        _log_web_warning("取得知識庫狀態", e)
        error = _sanitize_web_error(e)

    return templates.TemplateResponse(
        request,
        "kb.html",
        {"stats": stats, "error": error},
    )


# ── 知識庫搜尋（HTMX 局部回應） ─────────────────────
@web_app.post("/kb/search", response_class=HTMLResponse)
async def kb_search(
    request: Request,
    query: str = Form(...),
    n_results: int = Form(5),
):
    """語意搜尋知識庫，回傳 HTMX 局部 HTML"""
    error = None
    results = None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{_API_BASE}/api/v1/kb/search",
                headers=_api_headers(),
                json={
                    "query": query,
                    "n_results": n_results,
                },
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("success"):
                results = data.get("results", [])
            else:
                error = data.get("error") or data.get("detail") or f"HTTP {resp.status_code}"
    except _WEB_UI_EXCEPTIONS as e:
        _log_web_warning("知識庫搜尋", e)
        error = _sanitize_web_error(e)

    return templates.TemplateResponse(
        request,
        "kb_results.html",
        {"results": results, "error": error},
    )


# ── 歷史紀錄 ──────────────────────────────────────────
@web_app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    """生成歷史紀錄頁面"""
    records = []
    error = None
    history_path = Path(
        resolve_state_read_path(
            ".gov-ai-history.json",
            cwd=str(_PROJECT_ROOT),
            state_dir=_WEB_UI_STATE_DIR,
        ),
    )

    try:
        if history_path.exists():
            data = json.loads(history_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                records = list(reversed(data))[:100]
    except _WEB_UI_EXCEPTIONS as e:
        _log_web_warning("讀取歷史紀錄", e)
        error = _sanitize_web_error(e)

    return templates.TemplateResponse(
        request,
        "history.html",
        {"records": records, "error": error},
    )


# ── 批次處理 ──────────────────────────────────────────
@web_app.get("/batch", response_class=HTMLResponse)
async def batch_page(request: Request):
    """批次處理頁面"""
    return templates.TemplateResponse(request, "batch.html")


# ── 操作指南 ──────────────────────────────────────────
@web_app.get("/guide", response_class=HTMLResponse)
async def guide_page(request: Request):
    """操作指南頁面"""
    return templates.TemplateResponse(request, "guide.html")


# ── 設定 ──────────────────────────────────────────────
@web_app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    """顯示目前系統設定"""
    health = None
    error = None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{_API_BASE}/api/v1/health", headers=_api_headers())
            if resp.status_code == 200:
                health = resp.json()
    except _WEB_UI_EXCEPTIONS as e:
        _log_web_warning("取得設定頁資料", e)
        error = _sanitize_web_error(e)

    return templates.TemplateResponse(
        request,
        "config.html",
        {"health": health, "error": error},
    )


# ── 效能監控 ──────────────────────────────────────────
@web_app.get("/metrics", response_class=HTMLResponse)
async def metrics_page(request: Request):
    """效能監控頁面"""
    return templates.TemplateResponse(request, "metrics.html")


@web_app.get("/metrics/data", response_class=HTMLResponse)
async def metrics_data(request: Request):
    """效能監控 HTMX 局部回應"""
    metrics = None
    error = None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{_API_BASE}/api/v1/metrics", headers=_api_headers())
            if resp.status_code == 200:
                metrics = resp.json()
            else:
                error = f"API 回傳 HTTP {resp.status_code}"
    except _WEB_UI_EXCEPTIONS as e:
        _log_web_warning("取得效能指標", e)
        error = _sanitize_web_error(e)

    return templates.TemplateResponse(
        request,
        "metrics_partial.html",
        {"metrics": metrics, "error": error},
    )


# ── 詳細審查報告 API ──────────────────────────────────
@web_app.get("/api/v1/detailed-review", response_class=JSONResponse)
async def detailed_review(session_id: str = ""):
    """
    代理轉發至後端 API 取得完整 QA 報告 JSON。
    此端點供前端 HTMX 或外部系統使用。
    """
    if not session_id:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "缺少 session_id 參數"},
        )
    # session_id 格式驗證：僅允許英數字與連字號
    import re as _re
    if not _re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", session_id):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "session_id 格式無效"},
        )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{_API_BASE}/api/v1/detailed-review",
                headers=_api_headers(),
                params={"session_id": session_id},
            )
            return JSONResponse(
                status_code=resp.status_code,
                content=resp.json(),
            )
    except _WEB_UI_EXCEPTIONS as e:
        _log_web_warning("取得詳細審查報告", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": _sanitize_web_error(e)},
        )
