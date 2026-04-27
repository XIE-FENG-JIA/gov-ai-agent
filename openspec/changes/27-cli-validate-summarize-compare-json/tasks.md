# Epic 27 Tasks — CLI validate、summarize、compare JSON 格式

- [x] T27.1：稽核 `validate_cmd.py`、`summarize_cmd.py`、`compare_cmd.py` 現有輸出結構，
      確認需要 JSON 化的欄位清單；更新 `docs/cli-output-audit.md` 補對應條目
- [x] T27.2：在 `validate_cmd.py` 加入 `--format {text,json}` 選項；JSON 輸出含
      `{"checks": [{"name": str, "passed": bool, "message": str}], "pass_count": int, "total": int, "passed": bool}`；
      `text` 路徑與現有 Rich Table 格式一致
- [x] T27.3：在 `summarize_cmd.py` 加入 `--format {text,json}` 選項；JSON 輸出含
      `{"title": str, "summary": str, "source_file": str, "max_length": int}`；
      `text` 路徑與現有 Rich Panel 格式一致
- [x] T27.4：在 `compare_cmd.py` 加入 `--format {text,json}` 選項；JSON 輸出含
      `{"added": int, "removed": int, "identical": bool, "diff_lines": list[str]}`；
      `text` 路徑與現有 Rich diff 格式一致
- [x] T27.5：新增 `tests/test_cli_validate_summarize_compare_json.py`（15 tests）：
      (a) validate JSON schema 欄位完整性；(b) summarize JSON schema 欄位完整性；
      (c) compare JSON schema 欄位完整性；(d) `text` 預設不含 JSON；
      (e) 非法 `--format` 值報錯；(f) 全量回歸 PASS；
      更新 `CONTRIBUTING.md` 補 CLI Output Format 節範例
