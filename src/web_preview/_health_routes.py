"""Metrics and health monitoring routes for Web UI — extracted from app.py.

Extracted from src/web_preview/app.py (T-FAT-WATCH-CUT-V6).
Register via: web_app.include_router(create_router(templates, api_base))
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.web_preview._helpers import (
    _WEB_UI_EXCEPTIONS,
    _api_headers,
    _log_web_warning,
    _sanitize_web_error,
)


def create_router(templates: Jinja2Templates, api_base: str) -> APIRouter:
    """Build and return a FastAPI router with /metrics routes pre-configured."""
    router = APIRouter()

    @router.get("/metrics", response_class=HTMLResponse)
    async def metrics_page(request: Request) -> HTMLResponse:
        """效能監控頁面"""
        return templates.TemplateResponse(request, "metrics.html")

    @router.get("/metrics/data", response_class=HTMLResponse)
    async def metrics_data(request: Request) -> HTMLResponse:
        """效能監控 HTMX 局部回應"""
        metrics = None
        error = None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{api_base}/api/v1/metrics", headers=_api_headers())
                if resp.status_code == 200:
                    metrics = resp.json()
                else:
                    error = f"API 回傳 HTTP {resp.status_code}"
        except _WEB_UI_EXCEPTIONS as exc:
            _log_web_warning("取得效能指標", exc)
            error = _sanitize_web_error(exc)
        return templates.TemplateResponse(
            request,
            "metrics_partial.html",
            {"metrics": metrics, "error": error},
        )

    return router
