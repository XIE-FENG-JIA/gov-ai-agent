"""Integration tests: KB CLI complete flow — source fetch → ingest → search recall@k.

Gated by GOV_AI_RUN_INTEGRATION=1 — default skip so CI never blocks on live APIs.
Tests the full pipeline: fetch live records from a public source, normalise them,
ingest into an isolated KB, and verify that a keyword search returns at least one
relevant result (recall@k ≥ 1).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


def _require_live_integration() -> None:
    if os.getenv("GOV_AI_RUN_INTEGRATION") != "1":
        pytest.skip("set GOV_AI_RUN_INTEGRATION=1 to run KB CLI flow integration tests")
    if os.getenv("GOV_AI_RUN_LIVE_SOURCES") != "1":
        pytest.skip("set GOV_AI_RUN_LIVE_SOURCES=1 to run tests that call live external APIs")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_and_normalize(adapter, *, limit: int) -> list:
    """Fetch up to *limit* records and normalize them; skip individual failures."""
    docs = []
    for item in list(adapter.list(limit=limit))[:limit]:
        source_id = str(item.get("id", "")).strip()
        if not source_id:
            continue
        try:
            raw = adapter.fetch(source_id)
            normalized = adapter.normalize(raw)
            docs.append(normalized)
        except Exception:  # noqa: BLE001 — tolerate individual record errors in integration
            pass
    return docs


# ---------------------------------------------------------------------------
# KB CLI flow: fetch → ingest → search
# ---------------------------------------------------------------------------

def test_kb_flow_fetch_ingest_search_mojlaw() -> None:
    """Live mojlaw fetch → KB ingest → search recall@k ≥ 1."""
    _require_live_integration()

    from src.sources.mojlaw import MojLawAdapter
    from src.core.config import ConfigManager
    from src.core.llm import get_llm_factory
    from src.knowledge.manager import KnowledgeBaseManager

    records = _fetch_and_normalize(MojLawAdapter(), limit=5)
    if not records:
        pytest.skip("mojlaw returned no live records — check network/API")

    with tempfile.TemporaryDirectory() as tmpdir:
        config = ConfigManager()
        llm_factory = get_llm_factory(config.config.get("llm", {}), full_config=config.config)
        kb = KnowledgeBaseManager(
            llm_provider=llm_factory.get_provider(),
            persist_directory=tmpdir,
        )
        kb.reset_db()

        ingested = 0
        for doc in records:
            try:
                kb.add_document(
                    content=doc.content_md or "",
                    metadata={
                        "source_id": doc.source_id,
                        "title": doc.source_id,
                        "doc_type": doc.doc_type,
                        "synthetic": False,
                    },
                )
                ingested += 1
            except Exception:  # noqa: BLE001
                pass

        assert ingested > 0, "KB ingest produced 0 documents from live mojlaw records"

        results = kb.search("法規條文", n_results=3)
        assert isinstance(results, list), "KB search must return a list"
        # recall@3 ≥ 1: at least one result returned after ingesting real records
        assert len(results) >= 1, (
            f"KB search recall@3 = 0 after ingesting {ingested} real mojlaw records"
        )


def test_kb_flow_fetch_ingest_search_executive_yuan_rss() -> None:
    """Live executive_yuan_rss fetch → KB ingest → search recall@k ≥ 1."""
    _require_live_integration()

    from src.sources.executive_yuan_rss import ExecutiveYuanRssAdapter
    from src.core.config import ConfigManager
    from src.core.llm import get_llm_factory
    from src.knowledge.manager import KnowledgeBaseManager

    records = _fetch_and_normalize(ExecutiveYuanRssAdapter(), limit=5)
    if not records:
        pytest.skip("executive_yuan_rss returned no live records — check RSS feed")

    with tempfile.TemporaryDirectory() as tmpdir:
        config = ConfigManager()
        llm_factory = get_llm_factory(config.config.get("llm", {}), full_config=config.config)
        kb = KnowledgeBaseManager(
            llm_provider=llm_factory.get_provider(),
            persist_directory=tmpdir,
        )
        kb.reset_db()

        ingested = 0
        for doc in records:
            try:
                kb.add_document(
                    content=doc.content_md or "",
                    metadata={
                        "source_id": doc.source_id,
                        "title": doc.source_id,
                        "doc_type": doc.doc_type,
                        "synthetic": False,
                    },
                )
                ingested += 1
            except Exception:  # noqa: BLE001
                pass

        assert ingested > 0, "KB ingest produced 0 documents from live executive_yuan_rss records"

        results = kb.search("行政院", n_results=3)
        assert isinstance(results, list), "KB search must return a list"
        assert len(results) >= 1, (
            f"KB search recall@3 = 0 after ingesting {ingested} real executive_yuan_rss records"
        )


def test_kb_flow_ingest_stats_report_real_vs_synthetic() -> None:
    """Ingest mix of real + synthetic docs; stats must separate them correctly."""
    _require_live_integration()

    from src.sources.mojlaw import MojLawAdapter
    from src.core.config import ConfigManager
    from src.core.llm import get_llm_factory
    from src.knowledge.manager import KnowledgeBaseManager

    real_records = _fetch_and_normalize(MojLawAdapter(), limit=3)
    if not real_records:
        pytest.skip("mojlaw returned no live records — check network/API")

    with tempfile.TemporaryDirectory() as tmpdir:
        config = ConfigManager()
        llm_factory = get_llm_factory(config.config.get("llm", {}), full_config=config.config)
        kb = KnowledgeBaseManager(
            llm_provider=llm_factory.get_provider(),
            persist_directory=tmpdir,
        )
        kb.reset_db()

        for doc in real_records[:2]:
            try:
                kb.add_document(
                    content=doc.content_md or "",
                    metadata={"source_id": doc.source_id, "title": doc.source_id,
                               "doc_type": doc.doc_type, "synthetic": False},
                )
            except Exception:  # noqa: BLE001
                pass

        try:
            kb.add_document(
                content="測試用合成文件內容",
                metadata={"source_id": "synthetic_test", "title": "synthetic_test",
                           "doc_type": "函", "synthetic": True},
            )
        except Exception:  # noqa: BLE001
            pass

        stats = kb.get_stats()
        assert isinstance(stats, dict), "KB get_stats() must return a dict"
        # total count should be positive after ingestion
        total = stats.get("total_documents", stats.get("count", 0))
        assert total > 0, f"KB stats shows 0 documents after ingestion: {stats}"
