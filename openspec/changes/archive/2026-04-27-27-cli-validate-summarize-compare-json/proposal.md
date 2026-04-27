# Epic 27 — CLI validate、summarize、compare JSON 格式

## 背景

Epic 24–26 為 `lint`、`cite`、`verify`、`kb search`、`stats`、`status`、`rewrite`、`generate`
加入 `--format {text,json}` 輸出模式，建立了統一規範。然而，`gov-ai validate`、
`gov-ai summarize`、`gov-ai compare` 三個常用指令仍僅支援人類可讀的 Rich 格式，
無法在自動化工作流程或 CI/CD 管線中程式化消費輸出。

## 問題陳述

1. `gov-ai validate` 輸出依賴 Rich Table 呈現驗證結果，無法 pipe 給下游工具解析。
2. `gov-ai summarize` 輸出依賴 Rich Panel 呈現摘要，難以在自動化場景擷取結構化資料。
3. `gov-ai compare` 輸出依賴 Rich diff 顯示，統計數字無法直接以程式解析。
4. 三個指令的輸出模式與 epic 24–26 建立的 `--format {text,json}` 規範不一致。

## 解決方案

延伸 `--format {text,json}` 規範到 `validate`、`summarize`、`compare` 指令：

- **`gov-ai validate --format json`**：
  輸出 `{"checks": [{"name": str, "passed": bool, "message": str}], "pass_count": int, "total": int, "passed": bool}`
- **`gov-ai summarize --format json`**：
  輸出 `{"title": str, "summary": str, "source_file": str, "max_length": int}`
- **`gov-ai compare --format json`**：
  輸出 `{"added": int, "removed": int, "identical": bool, "diff_lines": list[str]}`

使用 `json.dumps()` 直出，保持向後相容（預設仍為 `text`）。

## 驗收條件

- AC-1：`gov-ai validate --format json` 輸出合法 JSON，含 `checks`、`pass_count`、`total`、`passed` 欄位。
- AC-2：`gov-ai summarize --format json` 輸出合法 JSON，含 `title`、`summary`、`source_file`、`max_length` 欄位。
- AC-3：`gov-ai compare --format json` 輸出合法 JSON，含 `added`、`removed`、`identical`、`diff_lines` 欄位。
- AC-4：預設 `--format text` 行為與現有測試完全向後相容（全量回歸 PASS）。
- AC-5：新增 `tests/test_cli_validate_summarize_compare_json.py`，覆蓋 JSON schema 驗證（≥ 9 tests）。

## 影響範圍

- `src/cli/validate_cmd.py`
- `src/cli/summarize_cmd.py`
- `src/cli/compare_cmd.py`
- `tests/test_cli_validate_summarize_compare_json.py`（新增）
- `docs/cli-output-audit.md`（補 validate/summarize/compare 條目）
- `CONTRIBUTING.md`（補 CLI Output Format 節範例）
