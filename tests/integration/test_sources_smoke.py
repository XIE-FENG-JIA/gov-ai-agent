from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest
import requests

from src.core.models import PublicGovDoc
from src.sources.datagovtw import DataGovTwAdapter
from src.sources.executive_yuan_rss import ExecutiveYuanRssAdapter
from src.sources.fda_api import FdaApiAdapter
from src.sources.mohw_rss import MohwRssAdapter
from src.sources.mojlaw import MojLawAdapter


pytestmark = pytest.mark.integration


def _live_sources_enabled() -> bool:
    return (
        os.getenv("GOV_AI_RUN_INTEGRATION") == "1"
        and os.getenv("GOV_AI_RUN_LIVE_SOURCES") == "1"
    )


def _require_live_sources() -> None:
    if os.getenv("GOV_AI_RUN_INTEGRATION") != "1":
        pytest.skip("set GOV_AI_RUN_INTEGRATION=1 to run live source smoke tests")
    if os.getenv("GOV_AI_RUN_LIVE_SOURCES") != "1":
        pytest.skip("set GOV_AI_RUN_LIVE_SOURCES=1 to run tests that call live external APIs")


def _disable_fixtures(adapter: object) -> None:
    """Force integration smoke to fail on live-request errors instead of silently using fixtures."""
    sentinel = Path(__file__).resolve().parent / "__fixtures_disabled__"
    if hasattr(adapter, "fixture_dir"):
        adapter.fixture_dir = sentinel
    if hasattr(adapter, "fixture_path"):
        adapter.fixture_path = sentinel


class TrackingSession(requests.Session):
    def __init__(self) -> None:
        super().__init__()
        self.request_times: list[float] = []

    def request(self, *args, **kwargs):  # type: ignore[override]
        self.request_times.append(time.perf_counter())
        return super().request(*args, **kwargs)


@dataclass(frozen=True)
class SmokeCase:
    source_key: str
    adapter_factory: Callable[[TrackingSession], object]
    live_loader: Callable[[object], object]


SMOKE_CASES = [
    SmokeCase(
        source_key="mojlaw",
        adapter_factory=lambda session: MojLawAdapter(session=session),
        live_loader=lambda adapter: adapter._load_catalog(force_refresh=True),
    ),
    SmokeCase(
        source_key="datagovtw",
        adapter_factory=lambda session: DataGovTwAdapter(session=session),
        live_loader=lambda adapter: adapter._load_catalog(limit=3, force_refresh=True),
    ),
    SmokeCase(
        source_key="executiveyuanrss",
        adapter_factory=lambda session: ExecutiveYuanRssAdapter(session=session),
        live_loader=lambda adapter: adapter._load_feed(force_refresh=True),
    ),
    SmokeCase(
        source_key="mohw",
        adapter_factory=lambda session: MohwRssAdapter(session=session),
        live_loader=lambda adapter: adapter._load_feed(force_refresh=True),
    ),
    SmokeCase(
        source_key="fda",
        adapter_factory=lambda session: FdaApiAdapter(session=session),
        live_loader=lambda adapter: adapter._load_catalog(limit=3, force_refresh=True),
    ),
]


@pytest.mark.parametrize("case", SMOKE_CASES, ids=lambda case: case.source_key)
def test_live_source_smoke_normalizes_one_public_doc(case: SmokeCase) -> None:
    _require_live_sources()

    session = TrackingSession()
    adapter = case.adapter_factory(session)
    _disable_fixtures(adapter)

    docs = list(adapter.list(limit=1))

    assert docs, f"{case.source_key} returned no live documents"
    assert docs[0]["id"]
    raw = adapter.fetch(docs[0]["id"])
    normalized = adapter.normalize(raw)

    assert isinstance(normalized, PublicGovDoc)
    assert normalized.source_id
    assert normalized.source_url.startswith("http")
    assert normalized.source_agency
    assert normalized.content_md.strip()
    assert normalized.synthetic is False
    assert adapter.rate_limit >= 2.0
    assert session.request_times, f"{case.source_key} did not issue a live request"


@pytest.mark.parametrize("case", SMOKE_CASES, ids=lambda case: case.source_key)
def test_live_source_loader_respects_default_rate_limit(case: SmokeCase) -> None:
    _require_live_sources()

    session = TrackingSession()
    adapter = case.adapter_factory(session)
    _disable_fixtures(adapter)

    case.live_loader(adapter)
    case.live_loader(adapter)

    assert len(session.request_times) >= 2, f"{case.source_key} did not issue two live requests"
    assert session.request_times[1] - session.request_times[0] >= adapter.rate_limit - 0.05
