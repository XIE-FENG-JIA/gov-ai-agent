"""Integration test conftest — mock LLM injection for meeting/smoke routes.

T-LITELLM-WARNING-CLOSE-V2: Extend mock injection to integration meeting routes
to prevent ``PydanticSerializationUnexpectedValue`` UserWarning emitted by real
LiteLLM response serialization when uvicorn servers call ``get_llm()``.

Strategy: pre-inject ``MockLLMProvider`` into ``src.api.dependencies._llm`` at
session start (before any module-scoped server fixture). Since ``get_llm()``
short-circuits on ``_llm is not None``, the server's lifespan never instantiates
a real LiteLLM provider, preventing all pydantic serialization warnings.
"""
from __future__ import annotations

import pytest

import src.api.dependencies as _deps
from src.core.llm import MockLLMProvider


@pytest.fixture(scope="session", autouse=True)
def _inject_mock_llm_for_integration():
    """Pre-inject MockLLMProvider so uvicorn servers never call real LiteLLM.

    Runs once at session start — before any module-scoped server fixture
    (``live_api_server``, ``meeting_api_server``, etc.) that spins up uvicorn.
    The mock is in place when ``lifespan`` calls ``get_llm()``, which returns
    the already-set ``_deps._llm`` immediately without re-initialising.
    """
    original_llm = _deps._llm
    _deps._llm = MockLLMProvider({"model": "mock-model"})
    yield
    _deps._llm = original_llm
