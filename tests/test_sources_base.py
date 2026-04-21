from __future__ import annotations

import inspect

import pytest

from src.sources.base import BaseSourceAdapter
from src.sources.datagovtw import DataGovTwAdapter
from src.sources.executive_yuan_rss import ExecutiveYuanRssAdapter
from src.sources.fda_api import FdaApiAdapter
from src.sources.mohw_rss import MohwRssAdapter
from src.sources.mojlaw import MojLawAdapter
from src.sources.pcc import PccAdapter


def test_base_source_adapter_is_abstract() -> None:
    with pytest.raises(TypeError):
        BaseSourceAdapter()


def test_base_source_adapter_declares_required_methods() -> None:
    assert BaseSourceAdapter.__abstractmethods__ == {"fetch", "list", "normalize"}


def test_mojlaw_adapter_instantiates() -> None:
    adapter = MojLawAdapter()
    assert adapter is not None


def test_source_adapters_expose_common_list_signature() -> None:
    expected = ("self", "since_date", "limit")

    assert tuple(inspect.signature(BaseSourceAdapter.list).parameters) == expected
    assert tuple(inspect.signature(MojLawAdapter.list).parameters) == expected
    assert tuple(inspect.signature(DataGovTwAdapter.list).parameters) == expected
    assert tuple(inspect.signature(ExecutiveYuanRssAdapter.list).parameters) == expected
    assert tuple(inspect.signature(FdaApiAdapter.list).parameters) == expected
    assert tuple(inspect.signature(MohwRssAdapter.list).parameters) == expected
    assert tuple(inspect.signature(PccAdapter.list).parameters) == expected
