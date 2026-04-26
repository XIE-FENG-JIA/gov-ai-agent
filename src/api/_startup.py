"""Startup helpers extracted from app.py to keep it under the 260-line fat limit."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import src.api.middleware as _mw
from src.api.dependencies import get_config

logger = logging.getLogger(__name__)


def _preflight_check() -> None:
    """Run startup checks without blocking the server from booting."""
    config = get_config()
    llm_config = config.get("llm", {})

    provider = llm_config.get("provider", "ollama")
    api_key = llm_config.get("api_key", "")

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
        logger.warning("PREFLIGHT: 知識庫路徑 '%s' 不存在，KB 將在首次使用時建立。", kb_path)

    workers = int(os.environ.get("API_WORKERS", "1"))
    if workers > 1:
        logger.warning(
            "PREFLIGHT: API_WORKERS=%d > 1，in-process 速率限制器在多進程模式下"
            "每個 worker 獨立計數，實際限流為 %d × %d = %d RPM。"
            "生產環境建議使用 Redis 實現跨進程速率限制。",
            workers, workers, _mw._RATE_LIMIT_RPM, workers * _mw._RATE_LIMIT_RPM,
        )

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
        "PREFLIGHT: provider=%s, model=%s, has_api_key=%s, kb_path=%s, auth_enabled=%s, api_keys_count=%d",
        provider,
        model,
        bool(api_key),
        kb_path,
        auth_enabled,
        len(api_keys),
    )


def _warmup_law_cache() -> None:
    """Warm law cache in background to avoid first-request latency."""
    try:
        from src.knowledge.realtime_lookup import LawVerifier

        verifier = LawVerifier()
        verifier._ensure_cache()
        logger.info("法規快取預熱完成。")
    except (ImportError, OSError, RuntimeError):
        logger.warning("法規快取預熱失敗，將於首次使用時重試。", exc_info=True)


def _cleanup_old_outputs() -> None:
    """Delete stale DOCX outputs older than 24 hours."""
    import time as _time
    from src.core.constants import OUTPUT_DIR

    if not OUTPUT_DIR.exists():
        return

    cutoff = _time.time() - 86400
    count = 0
    for path in OUTPUT_DIR.glob("*.docx"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                count += 1
        except OSError as exc:
            logger.debug("清理檔案 '%s' 失敗（可能被鎖定）: %s", path.name, exc)

    if count:
        logger.info("清理 %d 個超過 24 小時的輸出檔案", count)
