# Epic 26 — CLI rewrite & generate JSON 格式

## 背景

Epic 24/25 為 `lint`、`cite`、`verify`、`kb search`、`stats`、`status` 加入 `--format json`
輸出模式，建立了統一的 `--format {text,json}` 規範。然而，`gov-ai rewrite` 與
`gov-ai generate` 是本系統最核心的兩個指令，目前仍僅支援人類可讀的 Rich 格式，
無法在 CI/CD 管線、後處理腳本或測試框架中程式化消費輸出。

## 問題陳述

1. `gov-ai rewrite` 輸出依賴 Rich Panel 呈現改寫結果，無法 pipe 給下游工具解析。
2. `gov-ai generate` 輸出依賴 Rich Panel 呈現公文草稿，難以在自動化場景中擷取結構化資料。
3. 兩個核心指令的輸出模式與 epic 24/25 建立的 `--format {text,json}` 規範不一致。

## 解決方案

延伸 `--format {text,json}` 規範到 `rewrite` 與 `generate` 指令：

- **`gov-ai rewrite --format json`**：
  輸出 `{"rewritten": str, "doc_type": str, "score": float|null, "issues": list[str]}`
- **`gov-ai generate --format json`**：
  輸出 `{"output": str, "doc_type": str, "score": float|null, "elapsed_sec": float|null}`

使用 `json.dumps()` 直出，保持向後相容（預設仍為 `text`）。

## 驗收條件

- AC-1：`gov-ai rewrite --format json` 輸出合法 JSON，含 `rewritten`、`doc_type`、`score`、`issues` 欄位。
- AC-2：`gov-ai generate --format json` 輸出合法 JSON，含 `output`、`doc_type`、`score`、`elapsed_sec` 欄位。
- AC-3：預設 `--format text` 行為與現有測試完全向後相容（全量回歸 PASS）。
- AC-4：新增 `tests/test_cli_rewrite_generate_json.py`，覆蓋 JSON schema 驗證（≥ 8 tests）。
- AC-5：非法 `--format` 值給出明確 error 訊息（與 epic 24/25 規範一致）。

## 影響範圍

- `src/cli/rewrite_cmd.py`
- `src/cli/generate/` (生成群組主流程)
- `tests/test_cli_rewrite_generate_json.py`（新增）
- `docs/cli-output-audit.md`（補 rewrite/generate 條目）
- `CONTRIBUTING.md`（補 CLI Output Format 節 rewrite/generate 範例）
