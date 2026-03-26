"""
API 工具函式
============

跨路由共用的工具函式：IP 取得、錯誤清理、結果轉換、非同步執行器。
"""

import asyncio
import ipaddress
import logging
import os
import re
from typing import Any

from fastapi import Request

from src.core.review_models import ReviewResult
from src.api.models import SingleAgentReviewResponse

logger = logging.getLogger(__name__)

# 單一 Agent 呼叫預設超時（秒）
ENDPOINT_TIMEOUT = int(os.environ.get("API_ENDPOINT_TIMEOUT", "180"))
# 完整 meeting 流程超時（秒）— 含多輪審查，需要更長
MEETING_TIMEOUT = int(os.environ.get("API_MEETING_TIMEOUT", "600"))
# 批次處理總體超時（秒）— 防止大量項目導致 HTTP 連線無限掛起
BATCH_TOTAL_TIMEOUT = int(os.environ.get("API_BATCH_TOTAL_TIMEOUT", "3600"))

# X-Forwarded-For 支援（反向代理後的真實 IP 提取）
_TRUST_PROXY = os.environ.get("TRUST_PROXY", "false").lower() == "true"


def _get_client_ip(request: Request) -> str:
    """提取客戶端真實 IP。

    當 TRUST_PROXY=true 時，嘗試從 X-Forwarded-For 標頭中取得最左邊的
    合法 IP 地址（支援 IPv4 和 IPv6）。否則回退為 request.client.host。
    """
    if _TRUST_PROXY:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            # 取最左邊（最原始的客戶端 IP），使用 ipaddress 驗證
            first_ip = forwarded.split(",")[0].strip()
            try:
                ipaddress.ip_address(first_ip)
                return first_ip
            except ValueError:
                pass
    return request.client.host if request.client else "unknown"


# 錯誤映射表 — 單一真相來源（Single Source of Truth）
# 新增異常類型只需在此處加一行，_sanitize_error 和 _get_error_code 自動同步。
# 格式：異常類型名稱 → (錯誤代碼, 使用者安全訊息)
_ERROR_REGISTRY: dict[str, tuple[str, str]] = {
    "ValueError":             ("INVALID_INPUT",        "輸入資料不符合預期格式，請檢查請求參數。"),
    "ValidationError":        ("VALIDATION_FAILED",    "請求資料驗證失敗，請檢查欄位格式。"),
    "TypeError":              ("TYPE_ERROR",           "請求參數類型錯誤，請檢查資料格式。"),
    "KeyError":               ("MISSING_FIELD",        "請求資料缺少必要欄位。"),
    "TimeoutError":           ("TIMEOUT",              "操作逾時，請稍後再試。"),
    "LLMTimeoutError":        ("LLM_TIMEOUT",          "LLM 生成逾時，請稍後再試或考慮縮短輸入長度。"),
    "CancelledError":         ("CANCELLED",            "操作已取消或逾時，請稍後再試。"),
    "ConnectionError":        ("LLM_CONNECTION_FAILED", "無法連線至 LLM 服務。若使用 Ollama，請確認已執行 ollama serve。"),
    "ConnectionRefusedError": ("LLM_CONNECTION_FAILED", "無法連線至 LLM 服務。若使用 Ollama，請確認已執行 ollama serve。"),
    "LLMConnectionError":     ("LLM_CONNECTION_FAILED", "無法連線至 LLM 服務。若使用 Ollama，請確認已執行 ollama serve。"),
    "LLMAuthError":           ("LLM_AUTH_FAILED",      "API Key 無效或已過期，請檢查設定檔中的 api_key。"),
    "LLMError":               ("LLM_ERROR",            "LLM 服務發生錯誤，請稍後再試。"),
    "FileNotFoundError":      ("CONFIG_NOT_FOUND",     "找不到設定檔。請在專案目錄建立 config.yaml。"),
}

_DEFAULT_ERROR_CODE = "INTERNAL_ERROR"
_DEFAULT_ERROR_MESSAGE = "伺服器內部錯誤，請稍後再試或聯繫管理員。"


def _sanitize_error(exc: Exception) -> str:
    """清理例外訊息，避免洩漏內部實作細節。僅回傳安全的錯誤描述。"""
    entry = _ERROR_REGISTRY.get(type(exc).__name__)
    return entry[1] if entry else _DEFAULT_ERROR_MESSAGE


def _get_error_code(exc: Exception) -> str:
    """根據例外類型回傳標準化錯誤代碼。"""
    entry = _ERROR_REGISTRY.get(type(exc).__name__)
    return entry[0] if entry else _DEFAULT_ERROR_CODE


def review_result_to_dict(result: ReviewResult) -> SingleAgentReviewResponse:
    """將 ReviewResult 轉換為 API 回應格式。"""
    return SingleAgentReviewResponse(
        agent_name=result.agent_name,
        score=result.score,
        confidence=result.confidence,
        issues=[
            {
                "category": i.category,
                "severity": i.severity,
                "risk_level": i.risk_level,
                "location": i.location,
                "description": i.description,
                "suggestion": i.suggestion,
            }
            for i in result.issues
        ],
        has_errors=result.has_errors,
    )


def _sanitize_output_filename(filename: str | None, session_id: str) -> str:
    """清理並驗證輸出檔名，防止路徑遍歷攻擊。

    驗證規則與 download endpoint 的 regex 對齊：只允許
    ``[a-zA-Z0-9_\\-.]`` 字元，確保存下來的檔案一定可被下載。
    """
    fallback = f"output_{session_id}.docx"
    if not filename:
        return fallback
    basename = os.path.basename(filename)
    if not basename or basename.startswith("."):
        return fallback
    # 去掉 .docx 後綴再驗證主名稱（與 download endpoint regex 一致）
    stem = basename.removesuffix(".docx")
    if not stem or not re.match(r"^[a-zA-Z0-9_\-\.]+$", stem):
        return fallback
    if not basename.endswith(".docx"):
        basename = stem + ".docx"
    return basename


async def run_in_executor(func: Any, timeout: int | None = None) -> Any:
    """將同步的阻塞函式包裝為在執行緒池中非同步執行，並加超時保護。

    Args:
        func: 要執行的同步函式
        timeout: 超時秒數（預設使用 ENDPOINT_TIMEOUT）
    """
    from src.api.dependencies import executor

    if timeout is None:
        timeout = ENDPOINT_TIMEOUT
    loop = asyncio.get_running_loop()
    return await asyncio.wait_for(
        loop.run_in_executor(executor, func),
        timeout=timeout,
    )
