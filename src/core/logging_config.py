"""統一日誌配置模組。

提供 setup_logging() 函式，供 CLI 入口（src/cli/main.py）和
API 入口（api_server.py）統一呼叫，確保全專案日誌格式一致。
"""

import logging
import os

# 標準日誌格式：時戳 [等級] 模組名: 訊息
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"

# 預設需要抑制的第三方庫（避免冗長日誌淹沒業務訊息）
_NOISY_LOGGERS = ("chromadb", "httpcore", "httpx", "urllib3", "LiteLLM")


def setup_logging(
    level: int | None = None,
    *,
    force: bool = False,
    suppress_noisy: bool = True,
) -> None:
    """配置全域日誌格式與等級。

    Args:
        level: 明確指定日誌等級（如 logging.DEBUG）。
               若為 None，從 LOG_LEVEL 環境變數讀取（預設 INFO）。
        force: 是否強制覆蓋既有配置（API 伺服器啟動時需要）。
        suppress_noisy: 是否將第三方庫的日誌等級提升至 WARNING。
    """
    if level is None:
        env_level = os.getenv("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, env_level, logging.INFO)

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATEFMT,
        force=force,
    )

    if suppress_noisy:
        for name in _NOISY_LOGGERS:
            logging.getLogger(name).setLevel(logging.WARNING)
