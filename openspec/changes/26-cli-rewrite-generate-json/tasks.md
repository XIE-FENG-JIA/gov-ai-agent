# Epic 26 Tasks — CLI rewrite & generate JSON 格式

- [x] T26.1：稽核 `rewrite_cmd.py` 與 `generate/` 現有輸出結構，
      確認需要 JSON 化的欄位清單；更新 `docs/cli-output-audit.md` 補 rewrite/generate 條目
- [x] T26.2：在 `rewrite_cmd.py` 加入 `--format {text,json}` 選項；JSON 輸出含
      `{"rewritten": str, "doc_type": str, "score": float|null, "issues": list[str]}`；
      `text` 路徑與現有 Rich 格式一致
- [x] T26.3：在 `generate/` 主指令加入 `--format {text,json}` 選項；JSON 輸出含
      `{"output": str, "doc_type": str, "score": float|null, "elapsed_sec": float|null}`；
      `text` 路徑與現有 Rich Panel 格式一致
- [x] T26.4：新增 `tests/test_cli_rewrite_generate_json.py`（≥ 8 tests）：
      (a) rewrite JSON schema 欄位完整性；(b) generate JSON schema 欄位完整性；
      (c) `text` 預設不含 JSON；(d) 非法 `--format` 值報錯；(e) 全量回歸 PASS
- [x] T26.5：更新 `CONTRIBUTING.md` 補 CLI Output Format 節（rewrite/generate JSON 範例）；
      `docs/cli-output-audit.md` 補完整 rewrite/generate 輸出欄位表
