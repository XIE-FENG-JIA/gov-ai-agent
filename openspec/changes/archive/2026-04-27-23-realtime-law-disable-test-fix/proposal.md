# Epic 23 — Realtime Law Disable Test-Fix

## 背景

`.env` 含有 `GOVAI_DISABLE_REALTIME_LAW=1`（2026-04-27 加入，因 law.moj.gov.tw 在外部 IP
封鎖），此設定導致 `_ensure_cache()` 在測試執行時走入「disable」分支，建立空 cache 並立即
回傳，完全繞過 `_request_with_retry` mock。

症狀：`tests/test_realtime_lookup.py` 有 6 個測試，`mock_req.call_count == 0`，法律
`law_exists=False`（預期為 True）。

## 根因

```
_ensure_cache():
    if os.environ.get("GOVAI_DISABLE_REALTIME_LAW"):   # ← .env 設 1
        LawVerifier._cache = _LawCacheEntry(data={})
        return                                           # ← mock 永遠不被呼叫
```

## 修復方案

在 `tests/test_realtime_lookup.py` 的 `_clear_caches` autouse fixture 中加入
`monkeypatch.delenv("GOVAI_DISABLE_REALTIME_LAW", raising=False)`，讓每個測試在執行前
暫時清除此環境變數，測試結束後由 monkeypatch 自動還原。

此修復不影響生產行為（`.env` 原值不變），僅確保 mock 測試路徑可正常執行。

## 驗收條件

- AC-1：`python -m pytest tests/test_realtime_lookup.py -q` → 48 passed（之前 42 passed / 6 failed）
- AC-2：`python -m pytest tests/test_realtime_lookup.py -q -n auto` → 48 passed
- AC-3：`.env` 仍含 `GOVAI_DISABLE_REALTIME_LAW=1`（生產設定不變）
- AC-4：全套回歸 `python -m pytest -q` 無新 failures
