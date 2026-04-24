"""Per-adapter quality-gate policy defaults."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class QualityPolicy:
    """Quality-gate settings for one ingest adapter."""

    expected_min_records: int = 1
    freshness_window_days: int = 365
    allow_fallback: bool = True


DEFAULT_QUALITY_POLICY = QualityPolicy()

QUALITY_CONFIG: dict[str, QualityPolicy] = {
    "mojlaw": QualityPolicy(expected_min_records=50, freshness_window_days=90, allow_fallback=False),
    "datagovtw": QualityPolicy(expected_min_records=10, freshness_window_days=30, allow_fallback=False),
    "executive_yuan_rss": QualityPolicy(expected_min_records=5, freshness_window_days=14, allow_fallback=False),
    "executiveyuanrss": QualityPolicy(expected_min_records=5, freshness_window_days=14, allow_fallback=False),
    "mohw": QualityPolicy(expected_min_records=5, freshness_window_days=14, allow_fallback=False),
    "fda": QualityPolicy(expected_min_records=1, freshness_window_days=30, allow_fallback=False),
    "pcc": QualityPolicy(expected_min_records=1, freshness_window_days=30, allow_fallback=False),
}


def get_quality_policy(adapter_name: str) -> QualityPolicy:
    """Return the configured quality policy for an adapter name."""

    normalized_name = adapter_name.strip().lower()
    policy = QUALITY_CONFIG.get(normalized_name)
    if policy is not None:
        return policy

    logger.warning(
        "quality gate policy missing for adapter '%s'; using permissive default %s",
        normalized_name or "<blank>",
        asdict(DEFAULT_QUALITY_POLICY),
    )
    return DEFAULT_QUALITY_POLICY
