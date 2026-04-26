"""Web UI 輔助函式 — 從 app.py 拆出的 env 解析與錯誤處理工具。"""
from __future__ import annotations

import logging
import os

import httpx

from src.api.dependencies import get_config

logger = logging.getLogger(__name__)

# ── 可預期的 Web UI 例外桶 ────────────────────────────
_WEB_UI_EXCEPTIONS = (
    httpx.HTTPError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)

# json.JSONDecodeError is a subclass of ValueError, included above


def _parse_env_int(name: str, default: int) -> int:
    """從環境變數解析整數，解析失敗時回傳預設值並記錄 warning。"""
    raw = os.environ.get(name, str(default))
    try:
        return int(raw)
    except ValueError:
        logger.warning("環境變數 %s=%r 不是整數，改用預設值 %d", name, raw, default)
        return default


def _parse_env_float(name: str, default: float) -> float:
    """從環境變數解析浮點數，解析失敗時回傳預設值並記錄 warning。"""
    raw = os.environ.get(name, str(default))
    try:
        return float(raw)
    except ValueError:
        logger.warning("環境變數 %s=%r 不是數值，改用預設值 %.2f", name, raw, default)
        return default


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


def _api_headers() -> dict[str, str]:
    """取得呼叫內部 API 所需的認證標頭。"""
    config = get_config()
    api_keys = config.get("api", {}).get("api_keys", [])
    if api_keys:
        return {"Authorization": f"Bearer {api_keys[0]}"}
    return {}
