# Epic 28 Tasks — Discord push integration 正式化

- [x] T28.1：補 `tests/test_discord_push_async.py`，覆蓋 `_post_discord` async 路徑
      (a) 成功路徑（mock httpx 201）；(b) 4xx 路徑（mock httpx 403）；
      (c) 網路錯誤路徑（httpx.TimeoutException）；全部測試 PASS
- [x] T28.2：在 `tests/test_api_server.py` 補 meeting endpoint discord push 整合測試；
      mock `_discord_push.schedule_push`，驗證 meeting success 時被呼叫一次；
      mock `_discord_push.schedule_push` 拋例外，驗證 meeting 仍回 success
- [x] T28.3：`CONTRIBUTING.md` 補 Discord Push 節；
      說明 `DISCORD_BOT_TOKEN` / `DISCORD_ALERT_CHANNEL_ID` env vars；
      說明未設時 skip / 設後 fire-and-forget 行為
- [x] T28.4：`scripts/sensor_refresh.py` 加 `check_discord_push()` 函數；
      sensor JSON 加 `discord_push: {token_set: bool, channel_set: bool}`；
      `--human` 輸出補 discord_push 行
- [x] T28.5：全量 `python -m pytest tests/ --ignore=tests/integration -q` PASS；
      sensor.json 更新；results.log + program.md 追加；git commit + push
