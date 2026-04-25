"""HTTP 重試輔助函式 — 供 realtime_lookup 模組使用。"""
from __future__ import annotations

import logging
import time

import requests

from src.core.constants import HTTP_DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = HTTP_DEFAULT_TIMEOUT
_MAX_RETRIES = 2
_BACKOFF_BASE = 2


def _request_with_retry(url: str, *, timeout: int = _HTTP_TIMEOUT) -> requests.Response:
    """帶重試的 HTTP GET（獨立於 BaseFetcher，供本模組使用）。"""
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
            if "SSL" in str(exc) or "CERTIFICATE" in str(exc):
                logger.error(
                    "SSL 憑證驗證失敗 %s，拒絕降級以防止 MITM 攻擊。"
                    "請確認目標伺服器憑證或網路環境。", url,
                )
                raise
            last_exc = exc
            if attempt < _MAX_RETRIES:
                time.sleep(_BACKOFF_BASE ** attempt)
    raise last_exc  # type: ignore[misc]
