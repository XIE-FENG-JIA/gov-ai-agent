# Epic 24 Tasks — CLI Output JSON Mode

- [x] T24.1：稽核 `lint_cmd`、`cite_cmd`、`verify_cmd`、`kb/search` 現有輸出結構，
      建立 `docs/cli-output-audit.md` 記錄各指令輸出欄位與回傳路徑
- [x] T24.2：在 `lint_cmd.py` 加入 `--format {text,json}` 選項；JSON 輸出含
      `{"issues": [...], "score": float, "pass": bool}`；`text` 路徑與現有行為一致
- [x] T24.3：在 `cite_cmd.py` 加入 `--format {text,json}` 選項；JSON 輸出含
      `{"citations": [...], "count": int}`；`verify_cmd.py` 同批加入
      `{"facts": [...], "verdict": "pass"|"fail"|"warn"}`
- [x] T24.4：在 `src/cli/kb/search.py`（或對應 kb 搜尋實作）加入
      `--format {text,json}` 選項；JSON 輸出含
      `{"results": [{"doc_id": str, "score": float, "snippet": str}], "count": int}`
- [x] T24.5：新增 `tests/test_cli_json_output.py`（≥ 8 tests）：
      (a) 各指令 JSON schema 欄位完整性；(b) `text` 預設不含 JSON；
      (c) 非法 `--format` 值給出明確 error；(d) 全量回歸 `pytest --ignore=tests/integration` PASS
