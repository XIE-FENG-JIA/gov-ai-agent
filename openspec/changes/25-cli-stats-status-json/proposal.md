# Epic 25 — CLI Stats & Status JSON Format

## 背景

Epic 24 為 `lint`、`cite`、`verify`、`kb search` 四個核心指令加入了 `--format json`
輸出模式。然而，`gov-ai stats` 與 `gov-ai status` 兩個儀表板指令目前仍僅支援
人類可讀的 Rich 格式，無法在 CI/CD 管線或腳本中程式化消費。

## 問題陳述

1. `gov-ai stats` 輸出依賴 Rich Panel/Table，無法 pipe 給下游工具解析。
2. `gov-ai status` 同樣依賴 Rich Table 格式，難以在自動化場景中取得結構化資料。
3. 兩個指令的輸出模式與 epic 24 建立的 `--format {text,json}` 規範不一致。

## 解決方案

延伸 epic 24 的統一 `--format {text,json}` 規範到 `stats` 與 `status` 指令：

- **`gov-ai stats --format json`**：輸出 `{"total": int, "success": int, "failed": int, "type_counts": {...}, "avg_score": float|null}`
- **`gov-ai status --format json`**：輸出 `{"config": {...}, "history_count": int, "feedback_count": int, "kb_status": str}`

使用 `json.dumps()` 直出，保持向後相容（預設仍為 `text`）。

## 驗收條件

- AC-1：`gov-ai stats --format json` 輸出合法 JSON，含 `total`、`success`、`failed`、`type_counts`、`avg_score` 欄位。
- AC-2：`gov-ai status --format json` 輸出合法 JSON，含 `config`、`history_count`、`feedback_count`、`kb_status` 欄位。
- AC-3：預設 `--format text` 行為與現有測試完全向後相容（全量回歸 PASS）。
- AC-4：新增 `tests/test_cli_stats_status_json.py`，覆蓋 JSON schema 驗證（≥ 8 tests）。
- AC-5：非法 `--format` 值給出明確 error 訊息（與 epic 24 規範一致）。

## 影響範圍

- `src/cli/stats_cmd.py`
- `src/cli/status_cmd.py`
- `tests/test_cli_stats_status_json.py`（新增）
- `docs/cli-output-audit.md`（補 stats/status 條目）
