"""Route-level API client auth for write endpoints."""

from __future__ import annotations

import hmac
import logging
import os
from collections.abc import Iterable

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)
_dev_mode_warned = False


def _iter_client_keys(raw_value: str) -> Iterable[str]:
    for chunk in raw_value.split(","):
        value = chunk.strip()
        if value:
            yield value


def get_api_client_keys() -> list[str]:
    """Read API client keys from env; empty means auth disabled for local dev."""
    raw_value = os.environ.get("API_CLIENT_KEY", "")
    return list(_iter_client_keys(raw_value))


def _warn_dev_mode_once() -> None:
    global _dev_mode_warned
    if _dev_mode_warned:
        return
    _dev_mode_warned = True
    logger.warning(
        "API_CLIENT_KEY 未設定，write endpoints 以 dev mode 開放。"
        "生產環境請設定 API_CLIENT_KEY 並使用 Bearer token。"
    )


def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> None:
    """Require Bearer API key when API_CLIENT_KEY is configured."""
    valid_keys = get_api_client_keys()
    if not valid_keys:
        _warn_dev_mode_once()
        return

    token = None
    if credentials is not None and credentials.scheme.lower() == "bearer":
        token = credentials.credentials.strip()

    if token and any(hmac.compare_digest(token, valid_key) for valid_key in valid_keys):
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未提供有效的 Bearer API key。",
        headers={"WWW-Authenticate": "Bearer"},
    )
