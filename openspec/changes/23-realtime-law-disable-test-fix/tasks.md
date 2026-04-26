# Epic 23 Tasks — Realtime Law Disable Test-Fix

- [x] T23.1：診斷 6 個 failing test 根因（`GOVAI_DISABLE_REALTIME_LAW=1` 在 `.env` bypass `_request_with_retry` mock）
- [x] T23.2：修復 `_clear_caches` fixture（加 `monkeypatch` 參數 + `monkeypatch.delenv("GOVAI_DISABLE_REALTIME_LAW", raising=False)`）
- [x] T23.3：驗證 48 passed（no-xdist: 6.9s + xdist -n8: 28.3s）
- [x] T23.4：確認 `.env` 生產設定未改動（`GOVAI_DISABLE_REALTIME_LAW=1` 仍在原位）

