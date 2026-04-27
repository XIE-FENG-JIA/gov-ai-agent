# Epic 25 Tasks — CLI Stats & Status JSON Format

- [x] T25.1：稽核 `stats_cmd.py` 與 `status_cmd.py` 現有輸出結構，
      確認需要 JSON 化的欄位清單；更新 `docs/cli-output-audit.md` 補 stats/status 條目
- [x] T25.2：在 `stats_cmd.py` 加入 `--format {text,json}` 選項；JSON 輸出含
      `{"total": int, "success": int, "failed": int, "type_counts": dict, "avg_score": float|null}`；
      `text` 路徑與現有 Rich 格式一致
- [x] T25.3：在 `status_cmd.py` 加入 `--format {text,json}` 選項；JSON 輸出含
      `{"config": dict, "history_count": int, "feedback_count": int, "kb_status": str}`；
      `text` 路徑與現有 Rich Table 格式一致
- [x] T25.4：新增 `tests/test_cli_stats_status_json.py`（≥ 8 tests）：
      (a) stats JSON schema 欄位完整性；(b) status JSON schema 欄位完整性；
      (c) `text` 預設不含 JSON；(d) 非法 `--format` 值報錯；(e) 全量回歸 PASS
- [x] T25.5：更新 `CONTRIBUTING.md` 補 CLI Output Format 節（stats/status JSON 範例）；
      `docs/cli-output-audit.md` 補完整 stats/status 輸出欄位表
