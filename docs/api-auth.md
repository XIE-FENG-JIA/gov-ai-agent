# API Bearer Auth

`API_CLIENT_KEY` 控制寫入型 API 端點的 Bearer 驗證。

## 設定

在 `.env` 或部署環境加入：

```env
API_CLIENT_KEY=prod-key-1,prod-key-2
```

- 逗號分隔代表多組 key，可做輪換。
- 空值代表 dev mode：route-level auth 放行，方便本機開發。
- 生產環境不要留空。

## 呼叫範例

```bash
curl -X POST http://127.0.0.1:8000/api/v1/meeting \
  -H "Authorization: Bearer prod-key-1" \
  -H "Content-Type: application/json" \
  -d "{\"user_input\":\"請寫一份函\",\"skip_review\":true,\"output_docx\":false}"
```

## 輪換 SOP

1. 先把新 key 加進 `API_CLIENT_KEY`，保留舊 key。
2. 更新呼叫端改用新 key。
3. 確認流量已切換後，再從 `API_CLIENT_KEY` 移除舊 key。
