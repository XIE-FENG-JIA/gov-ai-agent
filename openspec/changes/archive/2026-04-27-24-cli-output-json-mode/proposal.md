# Epic 24 — CLI Output JSON Mode

## 背景

目前 `gov-ai` CLI 各指令的輸出格式各異：部分指令輸出人類可讀的純文字，部分輸出
半結構化的混合格式。在 CI/CD 管線或腳本自動化場景中，缺乏統一的 JSON 輸出模式
導致難以解析結果。

## 問題陳述

1. `gov-ai lint`、`gov-ai cite`、`gov-ai verify` 等核心指令無法在腳本中可靠取得
   結構化輸出。
2. `gov-ai kb search` 目前以純文字呈現搜尋結果，無法直接 pipe 給下游工具。
3. 缺乏統一的 `--format` 參數規範（`text` / `json` / `jsonl`），各指令各自為政。

## 解決方案

新增統一的 `--format {text,json}` 選項到四個高頻 CLI 指令群組：
- **核心指令**：`lint`、`cite`、`verify`
- **知識庫指令**：`kb search`、`kb status`

使用 `rich.console.Console(force_terminal=False)` 或純 `json.dumps()` 輸出，
保持向後相容（預設仍為 `text`）。

## 驗收條件

- AC-1：`gov-ai lint <doc> --format json` 輸出合法 JSON，含 `issues`、`score`、`pass` 欄位。
- AC-2：`gov-ai cite <doc> --format json` 輸出合法 JSON，含 `citations` 陣列。
- AC-3：`gov-ai verify <doc> --format json` 輸出合法 JSON，含 `facts`、`verdict` 欄位。
- AC-4：`gov-ai kb search <query> --format json` 輸出合法 JSON，含 `results` 陣列。
- AC-5：預設 `--format text` 行為與現有測試完全向後相容（全量回歸 PASS）。
- AC-6：新增 `tests/test_cli_json_output.py`，覆蓋 4 個指令的 JSON schema 驗證。

## 影響範圍

- `src/cli/lint_cmd.py`
- `src/cli/cite_cmd.py`
- `src/cli/verify_cmd.py`
- `src/cli/kb/search.py`（或對應的 kb search 實作）
- `tests/test_cli_json_output.py`（新增）
- `CONTRIBUTING.md`（新增 CLI Output Format 節）
