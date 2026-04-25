"""KB CLI package.

Compatibility note for tests reading module source:
ingest logic keeps separate `deprecated_count` / `failed_count` counters and
reports `embedding 產生失敗` from `corpus.py`.
"""

from src.core.config import ConfigManager
from src.core.llm import get_llm_factory
from src.knowledge.manager import KnowledgeBaseManager

from ._shared import app, console, logger
from .corpus import _ingest_fetch_results, _init_kb, _sanitize_metadata, parse_markdown_with_metadata
from . import corpus as _corpus  # noqa: F401
from . import fetch_commands as _fetch_commands  # noqa: F401
from . import ingest as _ingest  # noqa: F401
from . import rebuild as _rebuild  # noqa: F401
from . import stats as _stats  # noqa: F401
from . import status as _status  # noqa: F401

__all__ = [
    "ConfigManager",
    "KnowledgeBaseManager",
    "app",
    "console",
    "get_llm_factory",
    "logger",
    "parse_markdown_with_metadata",
    "_ingest_fetch_results",
    "_init_kb",
    "_sanitize_metadata",
]
