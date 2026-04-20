import logging

from rich.console import Console

from src.core.llm import LLMProvider
from src.knowledge.manager import KnowledgeBaseManager
from src.integrations.open_notebook import IntegrationDisabled, IntegrationSetupError
from src.integrations.open_notebook.config import get_open_notebook_mode
from src.integrations.open_notebook.service import OpenNotebookAskRequest, OpenNotebookService

from .ask_service import WriterAskServiceMixin
from .cite import WriterCitationMixin
from .cleanup import WriterCleanupMixin
from .rewrite import WriterRewriteMixin
from .strategy import WriterStrategyMixin

logger = logging.getLogger(__name__)
console = Console()


class WriterAgent(
    WriterRewriteMixin,
    WriterAskServiceMixin,
    WriterCitationMixin,
    WriterCleanupMixin,
    WriterStrategyMixin,
):
    """
    撰寫 Agent：負責使用 RAG 產生公文初稿。
    """

    def __init__(self, llm_provider: LLMProvider, kb_manager: KnowledgeBaseManager) -> None:
        self.llm = llm_provider
        self.kb = kb_manager
        self._last_sources_list: list[dict] = []
        self._last_open_notebook_diagnostics: dict[str, str] = {}


__all__ = [
    "IntegrationDisabled",
    "IntegrationSetupError",
    "KnowledgeBaseManager",
    "LLMProvider",
    "OpenNotebookAskRequest",
    "OpenNotebookService",
    "WriterAgent",
    "get_open_notebook_mode",
]
