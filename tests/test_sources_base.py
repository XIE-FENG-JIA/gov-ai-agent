from __future__ import annotations

from datetime import date

import pytest

from src.sources.base import BaseSourceAdapter
from src.sources.mojlaw import MojLawAdapter


def test_base_source_adapter_is_abstract() -> None:
    with pytest.raises(TypeError):
        BaseSourceAdapter()


def test_base_source_adapter_declares_required_methods() -> None:
    assert BaseSourceAdapter.__abstractmethods__ == {"fetch", "list", "normalize"}


def test_mojlaw_adapter_stub_raises_not_implemented() -> None:
    adapter = MojLawAdapter()

    with pytest.raises(NotImplementedError):
        list(adapter.list(date(2026, 1, 1)))

    with pytest.raises(NotImplementedError):
        adapter.fetch("A0030055")

    with pytest.raises(NotImplementedError):
        adapter.normalize({"LawName": "公文程式條例"})
