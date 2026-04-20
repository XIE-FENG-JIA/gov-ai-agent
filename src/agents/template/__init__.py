"""Template engine package with backward-compatible exports."""

from src.agents.template.engine import TemplateEngine
from src.agents.template.helpers import _chinese_index, clean_markdown_artifacts, renumber_provisions

__all__ = [
    "TemplateEngine",
    "clean_markdown_artifacts",
    "renumber_provisions",
    "_chinese_index",
]
