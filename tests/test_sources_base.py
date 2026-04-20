from __future__ import annotations

import pytest

from src.sources.base import BaseSourceAdapter
from src.sources.mojlaw import MojLawAdapter


def test_base_source_adapter_is_abstract() -> None:
    with pytest.raises(TypeError):
        BaseSourceAdapter()


def test_base_source_adapter_declares_required_methods() -> None:
    assert BaseSourceAdapter.__abstractmethods__ == {"fetch", "list", "normalize"}


def test_mojlaw_adapter_instantiates() -> None:
    adapter = MojLawAdapter()
    assert adapter is not None
