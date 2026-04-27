# Epic 28 Proposal — Discord push integration 正式化

## 背景

`src/api/routes/workflow/_discord_push.py` 已作為 fire-and-forget 功能加入
meeting endpoint，在 QA 報告完成後即時推送 Discord embed。
但目前缺少：
1. endpoint 層整合測試（mock Discord API）
2. `DISCORD_BOT_TOKEN` / `DISCORD_ALERT_CHANNEL_ID` 設定說明
3. sensor 追蹤 discord_push 狀態
4. `_post_discord` async 路徑覆蓋（目前 unit tests 不跑 async 路徑）

## 目標

- T28.1：補 `tests/test_discord_push_async.py`，覆蓋 `_post_discord` async 路徑（mock httpx）
- T28.2：補 meeting endpoint 整合測試，驗證 schedule_push 被呼叫（mock _discord_push）
- T28.3：`CONTRIBUTING.md` 補 Discord Push 節（env vars / dry-run / skip 條件）
- T28.4：`sensor_refresh.py` 加 `discord_push` 欄位（token 設否 / last_push_ok）
- T28.5：全量回歸 PASS + commit + push

## 驗收條件

- `_post_discord` 成功路徑 + 4xx 路徑 + 網路錯誤路徑各一測試
- meeting endpoint 測試覆蓋 discord push 被呼叫的 happy path
- `CONTRIBUTING.md` 有 Discord Push 節
- `sensor.json` 有 `discord_push` 欄位
- 4080+ tests passed
