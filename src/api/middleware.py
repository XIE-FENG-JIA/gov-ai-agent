"""
中介層 — 限流、指標收集、安全標頭、API Key 認證
===============================================
"""

import logging
import os
import re
import time
import threading
import uuid
from collections import defaultdict
from typing import Any

import hmac
from fastapi import Request
from fastapi.responses import JSONResponse

from src.core.constants import API_VERSION
from src.api.dependencies import get_config
from src.api.helpers import _get_client_ip

logger = logging.getLogger(__name__)

# ============================================================
# Rate Limiting（簡易滑動視窗限流器）
# ============================================================

# 預設限流設定（可透過環境變數覆蓋）
_RATE_LIMIT_RPM = int(os.environ.get("RATE_LIMIT_RPM", "30"))  # 每分鐘請求上限
_RATE_LIMIT_WINDOW = 60  # 滑動視窗秒數


class _RateLimiter:
    """基於 IP 的簡易滑動視窗限流器（執行緒安全）。"""

    _CLEANUP_INTERVAL = 1000  # 每 N 次請求執行一次全域清理

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()
        self._request_counter = 0

    def check(self, client_ip: str) -> tuple[bool, int, int]:
        """檢查該 IP 是否允許請求；同時清理過期紀錄。執行緒安全。

        Returns:
            (allowed, remaining, reset_after_seconds)
        """
        with self._lock:
            now = time.monotonic()

            # 定期全域清理：移除只訪問一次後消失的 IP 之過期條目
            self._request_counter += 1
            if self._request_counter >= self._CLEANUP_INTERVAL:
                self._request_counter = 0
                expired_ips = [
                    ip for ip, ts in self._requests.items()
                    if not any(now - t < self.window for t in ts)
                ]
                for ip in expired_ips:
                    del self._requests[ip]

            timestamps = self._requests[client_ip]
            # 清理過期的時間戳
            valid = [t for t in timestamps if now - t < self.window]
            if not valid:
                # 該 IP 已無有效紀錄，移除舊的 defaultdict 條目避免記憶體洩漏
                # 但仍需記錄此次請求
                self._requests.pop(client_ip, None)
                self._requests[client_ip] = [now]
                return True, self.max_requests - 1, self.window
            self._requests[client_ip] = valid
            # 計算最早紀錄的重設時間
            reset_after = max(1, int(self.window - (now - valid[0])))
            if len(valid) >= self.max_requests:
                return False, 0, reset_after
            self._requests[client_ip].append(now)
            remaining = self.max_requests - len(self._requests[client_ip])
            return True, remaining, reset_after

    def is_allowed(self, client_ip: str) -> bool:
        """向後相容的簡易介面。"""
        allowed, _, _ = self.check(client_ip)
        return allowed


# 全域限流器實例
rate_limiter = _RateLimiter(_RATE_LIMIT_RPM, _RATE_LIMIT_WINDOW)


# ============================================================
# Metrics Collector（輕量級效能指標收集器）
# ============================================================

class _MetricsCollector:
    """簡易效能指標收集器（執行緒安全）。

    記錄請求總數、回應時間、活動執行緒數等指標，
    透過 GET /api/v1/metrics 端點查詢。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total_requests: int = 0
        self._total_response_time_ms: float = 0.0
        self._active_requests: int = 0
        self._cache_hits: int = 0
        self._cache_misses: int = 0

    def record_request_start(self) -> None:
        """記錄請求開始（增加活動請求計數）。"""
        with self._lock:
            self._active_requests += 1

    def record_request_end(self, elapsed_ms: float) -> None:
        """記錄請求結束（更新統計資料）。"""
        with self._lock:
            self._total_requests += 1
            self._total_response_time_ms += elapsed_ms
            self._active_requests = max(0, self._active_requests - 1)

    def record_cache_hit(self) -> None:
        """記錄快取命中。"""
        with self._lock:
            self._cache_hits += 1

    def record_cache_miss(self) -> None:
        """記錄快取未命中。"""
        with self._lock:
            self._cache_misses += 1

    def snapshot(self) -> dict[str, Any]:
        """取得目前指標快照（執行緒安全）。"""
        with self._lock:
            total = self._total_requests
            avg_ms = (
                round(self._total_response_time_ms / total, 2) if total > 0 else 0.0
            )
            cache_total = self._cache_hits + self._cache_misses
            hit_rate = (
                round(self._cache_hits / cache_total, 4) if cache_total > 0 else 0.0
            )
            return {
                "total_requests": total,
                "avg_response_time_ms": avg_ms,
                "active_requests": self._active_requests,
                "cache_hit_rate": hit_rate,
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
            }


# 全域 metrics 實例
metrics = _MetricsCollector()


# ============================================================
# API Key 認證
# ============================================================

# 免認證的公開路徑（健康檢查、文件頁面）
_PUBLIC_PATHS: frozenset[str] = frozenset({
    "/",
    "/api/v1/health",
    "/docs",
    "/redoc",
    "/openapi.json",
})


def _check_api_key(request: Request) -> bool | None:
    """檢查 API Key 認證。

    Returns:
        None  — 認證已停用或路徑免認證，跳過檢查
        True  — 認證通過
        False — 認證失敗
    """
    config = get_config()
    api_config = config.get("api", {})

    # 預設停用認證（向後相容）
    if not api_config.get("auth_enabled", False):
        return None

    # 公開路徑免認證
    if request.url.path in _PUBLIC_PATHS:
        return None

    api_keys: list[str] = api_config.get("api_keys", [])
    if not api_keys:
        # 啟用認證但未設定任何 key → 記錄警告，放行（避免鎖死自己）
        logger.warning(
            "API 認證已啟用但 api_keys 為空，所有請求將被放行。"
            "請在 config.yaml 的 api.api_keys 中設定至少一組 key。"
        )
        return None

    # 嘗試從 Authorization: Bearer <key> 取得
    auth_header = request.headers.get("Authorization", "")
    token: str | None = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()

    # 嘗試從 X-API-Key 標頭取得
    if not token:
        token = request.headers.get("X-API-Key", "").strip() or None

    if not token:
        return False

    # 使用恆定時間比較防止計時攻擊
    for valid_key in api_keys:
        if hmac.compare_digest(token, valid_key):
            return True

    return False


# X-Request-ID 驗證：僅允許英數字、連字號和底線，最長 64 字元
_REQUEST_ID_PATTERN = re.compile(r"^[a-zA-Z0-9\-_]{1,64}$")


# ============================================================
# 安全中介層：Rate Limiting + 安全標頭 + API Key 認證
# ============================================================

async def security_middleware(request: Request, call_next):
    """
    為所有回應添加安全標頭、請求追蹤 ID、API Key 認證，並對 POST 端點進行限流。

    處理順序：追蹤 ID → API Key 認證 → Rate Limiting → 路由處理 → 安全標頭。
    """
    # 請求追蹤 ID（優先使用客戶端提供的，但須通過格式驗證以防注入攻擊）
    raw_request_id = request.headers.get("X-Request-ID", "")
    if raw_request_id and _REQUEST_ID_PATTERN.match(raw_request_id):
        request_id = raw_request_id
    else:
        request_id = str(uuid.uuid4())[:12]
    request.state.request_id = request_id

    # API Key 認證檢查
    auth_result = _check_api_key(request)
    if auth_result is False:
        resp = JSONResponse(
            status_code=401,
            content={"detail": "未提供有效的 API Key。請使用 Authorization: Bearer <key> 或 X-API-Key: <key> 標頭。"},
        )
        resp.headers["X-Request-ID"] = request_id
        resp.headers["WWW-Authenticate"] = "Bearer"
        return resp

    # Rate limiting（POST 請求 + metrics 等敏感 GET 端點）
    _RATE_LIMITED_GET_PATHS = frozenset({"/api/v1/metrics"})
    rate_limit_headers: dict[str, str] = {}
    if request.method == "POST" or request.url.path in _RATE_LIMITED_GET_PATHS:
        client_ip = _get_client_ip(request)
        allowed, remaining, reset_after = rate_limiter.check(client_ip)
        rate_limit_headers = {
            "X-RateLimit-Limit": str(_RATE_LIMIT_RPM),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_after),
        }
        if not allowed:
            resp = JSONResponse(
                status_code=429,
                content={
                    "detail": "請求過於頻繁，請稍後再試。",
                    "retry_after_seconds": reset_after,
                },
            )
            resp.headers["Retry-After"] = str(reset_after)
            resp.headers["X-Request-ID"] = request_id
            for k, v in rate_limit_headers.items():
                resp.headers[k] = v
            return resp

    metrics.record_request_start()
    start_time = time.monotonic()
    response = await call_next(request)
    elapsed_ms = (time.monotonic() - start_time) * 1000
    metrics.record_request_end(elapsed_ms)

    # 安全標頭
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Content-Security-Policy"] = "default-src 'none'"
    if os.environ.get("HTTPS_ENABLED", "false").lower() == "true":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-API-Version"] = API_VERSION
    response.headers["X-Request-ID"] = request_id
    for k, v in rate_limit_headers.items():
        response.headers[k] = v

    # 請求日誌（跳過 health check 避免雜訊）
    path = request.url.path
    if path not in ("/", "/api/v1/health"):
        log_level = logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(
            log_level,
            "[%s] %s %s -> %d (%.0fms)",
            request_id, request.method, path,
            response.status_code, elapsed_ms,
        )

    return response
