"""Rate limiting helpers for API middleware."""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict

# 預設限流設定（可透過環境變數覆蓋）
_RATE_LIMIT_RPM = int(os.environ.get("RATE_LIMIT_RPM", "30"))
_RATE_LIMIT_WINDOW = 60


class _RateLimiter:
    """基於 IP 的簡易滑動視窗限流器（執行緒安全）。"""

    _CLEANUP_INTERVAL = 1000

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window = window_seconds
        self.max_ips = 10000
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()
        self._request_counter = 0

    def check(self, client_ip: str) -> tuple[bool, int, int]:
        """檢查該 IP 是否允許請求；同時清理過期紀錄。"""
        with self._lock:
            now = time.monotonic()

            self._request_counter += 1
            if self._request_counter >= self._CLEANUP_INTERVAL:
                self._request_counter = 0
                expired_ips = [
                    ip
                    for ip, ts in self._requests.items()
                    if not any(now - t < self.window for t in ts)
                ]
                for ip in expired_ips:
                    del self._requests[ip]

            if client_ip not in self._requests and len(self._requests) >= self.max_ips:
                expired_ips = [
                    ip
                    for ip, ts in self._requests.items()
                    if not any(now - t < self.window for t in ts)
                ]
                for ip in expired_ips:
                    del self._requests[ip]
                if len(self._requests) >= self.max_ips:
                    return False, 0, self.window

            timestamps = self._requests[client_ip]
            valid = [t for t in timestamps if now - t < self.window]
            if not valid:
                self._requests.pop(client_ip, None)
                self._requests[client_ip] = [now]
                return True, self.max_requests - 1, self.window

            self._requests[client_ip] = valid
            reset_after = max(1, int(self.window - (now - valid[0])))
            if len(valid) >= self.max_requests:
                return False, 0, reset_after

            self._requests[client_ip].append(now)
            remaining = self.max_requests - len(self._requests[client_ip])
            return True, remaining, reset_after

    def is_allowed(self, client_ip: str) -> bool:
        """向後相容的簡易介面。"""
        allowed, _, _ = self.check(client_ip)
        return allowed


rate_limiter = _RateLimiter(_RATE_LIMIT_RPM, _RATE_LIMIT_WINDOW)
