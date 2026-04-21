"""Metrics helpers for API middleware."""

from __future__ import annotations

import threading
from typing import Any


class _MetricsCollector:
    """簡易效能指標收集器（執行緒安全）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total_requests: int = 0
        self._total_response_time_ms: float = 0.0
        self._active_requests: int = 0
        self._cache_hits: int = 0
        self._cache_misses: int = 0

    def record_request_start(self) -> None:
        with self._lock:
            self._active_requests += 1

    def record_request_end(self, elapsed_ms: float) -> None:
        with self._lock:
            self._total_requests += 1
            self._total_response_time_ms += elapsed_ms
            self._active_requests = max(0, self._active_requests - 1)

    def record_cache_hit(self) -> None:
        with self._lock:
            self._cache_hits += 1

    def record_cache_miss(self) -> None:
        with self._lock:
            self._cache_misses += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            total = self._total_requests
            avg_ms = round(self._total_response_time_ms / total, 4) if total > 0 else 0.0
            cache_total = self._cache_hits + self._cache_misses
            hit_rate = round(self._cache_hits / cache_total, 4) if cache_total > 0 else 0.0
            return {
                "total_requests": total,
                "avg_response_time_ms": avg_ms,
                "active_requests": self._active_requests,
                "cache_hit_rate": hit_rate,
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
            }


metrics = _MetricsCollector()
