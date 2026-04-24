from __future__ import annotations

import logging

from src.sources.quality_config import DEFAULT_QUALITY_POLICY, QUALITY_CONFIG, get_quality_policy


def test_quality_config_covers_all_epic1_adapter_keys() -> None:
    assert QUALITY_CONFIG.keys() == {
        "datagovtw",
        "executive_yuan_rss",
        "executiveyuanrss",
        "fda",
        "mohw",
        "mojlaw",
        "pcc",
    }


def test_get_quality_policy_returns_configured_policy() -> None:
    policy = get_quality_policy("mojlaw")

    assert policy.expected_min_records == 50
    assert policy.freshness_window_days == 90
    assert policy.allow_fallback is False


def test_get_quality_policy_normalizes_case_and_aliases() -> None:
    policy = get_quality_policy("ExecutiveYuanRSS")

    assert policy == QUALITY_CONFIG["executiveyuanrss"]


def test_get_quality_policy_falls_back_to_permissive_default(caplog) -> None:
    with caplog.at_level(logging.WARNING):
        policy = get_quality_policy("unknown_source")

    assert policy == DEFAULT_QUALITY_POLICY
    assert "quality gate policy missing for adapter 'unknown_source'" in caplog.text
