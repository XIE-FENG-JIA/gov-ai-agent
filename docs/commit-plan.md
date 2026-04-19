# Commit Plan

更新時間：`2026-04-20 01:53:24`

## fix(api)

目標：API workflow、Web UI、CORS、詳細審查查詢、RALPH loop。

檔案：
- `api_server.py`
- `src/api/models.py`
- `src/api/routes/workflow.py`
- `src/web_preview/app.py`
- `src/web_preview/templates/config.html`
- `src/web_preview/templates/index.html`
- `tests/test_api_server.py`
- `tests/test_web_preview.py`

建議驗證：
- `pytest tests/test_api_server.py tests/test_web_preview.py`

## fix(cli)

目標：MiniMax provider 切換、CLI config/write guard、Markdown 編碼輸出、tmp 清理。

檔案：
- `.env.example`
- `README.md`
- `config.yaml`
- `config.yaml.example`
- `src/cli/config_tools.py`
- `src/cli/generate.py`
- `src/cli/quickstart.py`
- `src/cli/switcher.py`
- `src/cli/utils.py`
- `tests/test_cli_commands.py`
- `tests/test_config_tools_extra.py`
- `tests/test_quickstart.py`

建議驗證：
- `pytest tests/test_cli_commands.py tests/test_config_tools_extra.py tests/test_quickstart.py`

## fix(agents)

目標：writer 後處理、template 預設欄位、editor 最佳版本保留、checker 對 citation 追蹤標記降噪、繁簡轉換。

檔案：
- `src/agents/compliance_checker.py`
- `src/agents/editor.py`
- `src/agents/style_checker.py`
- `src/agents/template.py`
- `src/agents/writer.py`
- `src/assets/templates/han.j2`
- `src/utils/tw_check.py`
- `tests/test_agents.py`
- `tests/test_robustness.py`

建議驗證：
- `pytest tests/test_agents.py tests/test_robustness.py`

## fix(kb)

目標：`chromadb` lazy import recovery、collection name 穩定化、cache 測試對齊。

檔案：
- `src/knowledge/manager.py`
- `tests/test_knowledge_manager_cache.py`
- `tests/test_knowledge_manager_unit.py`

建議驗證：
- `pytest tests/test_knowledge_manager_cache.py tests/test_knowledge_manager_unit.py`

## fix(tests)

目標：benchmark scripts 與新增測試資產。

檔案：
- `scripts/build_benchmark_corpus.py`
- `scripts/run_blind_eval.py`
- `tests/test_benchmark_scripts.py`

建議驗證：
- `pytest tests/test_benchmark_scripts.py`

## chore

目標：工作流紀錄、ignore、規劃檔。

檔案：
- `.gitignore`
- `engineer-log.md`
- `program.md`
- `docs/commit-plan.md`

建議驗證：
- `git diff --check`

## untracked / local-only

先不要 commit：
- `.serena/`：本機工具快取與設定。
- `benchmark/*.json`：盲測輸出結果，屬產物，不是程式碼。
- `.spectra.yaml`：若要納入版本控制，應另開 `chore(spec)` commit；目前先維持待判定。

## blocker

- `2026-04-20 01:54` 實測 `git add -- docs/commit-plan.md program.md results.log` 仍失敗：
  - `fatal: Unable to create '.git/index.lock': Permission denied`
- `.git` ACL 含 explicit `Deny Write/Delete` 規則；`Get-Acl .git` 已可重現。
- `Test-Path .git\\index.lock` 當下為 `NO_LOCK`，表示不是殘留 lock file，而是 `.git` 目錄寫入權本身被拒。
- 進 `P0.5.b` 前先優先排除 `.git` 寫入限制，否則任何 `git add` / `git commit` 都會失敗。
