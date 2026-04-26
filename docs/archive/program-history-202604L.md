# Program History 202604L — v7.9-final/v7.9-sensor/v7.8 批次頭 + 07:50/05:55 歷史 P0 封存

> Archived from `program.md` on 2026-04-26 to keep the live program under the 250-line soft cap.

## 批次回合批頭（v7.9-final / v7.9-sensor / v7.8）

> **v7.9-final 後段（2026-04-26 /pua 深度回顧；五源 HEAD + sensor + pytest -n auto + 單跑 + git diff 獨立量測）**：
> - ⚠️ **pytest -n auto 全量**：`python -m pytest tests/ -q --ignore=tests/integration` = **3948 passed / 1 failed / 14 errors / 263.64s** —— 與 sensor `--human` 報「3950 passed / 0 failed」**不一致 → 漂白第七型 xdist race 隱藏失敗**
> - ⚠️ **單跑同檔全綠**：`pytest tests/test_kb_rebuild_cli.py` = 2 passed；`pytest tests/test_e2e_rewrite.py::...not_traceable` = 1 passed → race 確證 xdist worker collect 污染 + fixture 跨 worker state 漏洗
> - ⚠️ **工作樹 19 檔未入版**（196+/394- diff）：含全新 `src/cli/shared/` + `src/core/history_store.py`（T13.5 落地）+ `verify_cmd.py` 大幅瘦身 + `kb_data/regulation_doc_type_mapping.yaml` 144 行新資料 + 6 檔 tests 副改 + engineer-log 245 行清理 → **T-WORKTREE-FLUSH-LOOP4 升 P0**
> - ✅ **bare-except 3/3**（noqa/compat 全意保留）；fat ≥400=0 / yellow 6 / max=375（vs v7.9-sensor max 386 → -11 行）
> - ✅ **corpus 400**；engineer-log 102 / program.md 193 / results.log 737
> - ⚠️ **wrapper noise 仍佔 git log**：近 50 commit 36 條 chore(auto-engineer/copilot) = 28% semantic ratio；含 8 條 AUTO-RESCUE → T-COPILOT-WRAPPER-HOST-PATCH P1 連 6+ 輪未動，T-WORKTREE-COMMIT-FLUSH-MERGED P0 SLA < 24hr
> - ✅ **T-CLI-FAT-ROTATE-V3 Track A/B/C 14/14**（T13.1e shim 已刪；T13.7 premature gap 已實質補閉）
>
> **v7.9-sensor 後段（2026-04-26 00:15；HEAD + sensor + pytest + git log 四源獨立 cold-start）**：
> - ✅ **pytest 3950 passed / 0 failed / 42.79s**（vs v7.9 baseline 45.78s — runtime −6.5%；用例 +1）
> - ✅ **sensor_refresh.py exit 0**；`violations.hard = []`；soft = 1（auto_commit_rate 26.7% < 90%）
> - ✅ **bare-except 3 / 3 檔**（hard 紅線清零；全 noqa/compat 故意保留）
> - ✅ **fat ≥400 = 0 / yellow 9 / max=390**（ratchet ok 9/10）
> - ✅ **corpus 400 ≥ target 200**
> - ⚠️ **auto-commit 真語意率 26.7%（8/30）vs 90% 目標 = 3.4× 差距**（漂白第四型出現：`chore(copilot): batch round` 取代 `auto-engineer: patch` — lint 沒擋到；T-COPILOT-NOISE-PATCH 升 P0）
> - ⚠️ **ACL-V2 假閉**：`lib/common.sh:803 yolo_mode=on` 21:46 寫 DEPLOYED，22:05–22:38 連 8 條 [AUTO-RESCUE] = 修法未驗收；T-ACL-V2-VERIFY 升 P0
> - ✅ **openspec 治理閉環**：11 spec promote + Purpose backfill；`openspec/changes/` 僅剩 archive
> - ✅ **integration 9 個檔**（test_sources_smoke + 8 e2e）+ CI integration job 已 wire（`a48b656`），首跑驗收待補
>
> **v7.8 P0（本輪三件，全閉）**：
> 1. ✅ **T-HEADER-RESYNC-v6**（修上輪 3 處漂白：corpus 173→400 / auto-commit 46.7%→3.3% / pytest 3917/129s→3926/63s）
- [x] **T-SPEC-LAG-CLOSE-v2**（2026-04-25 閉；P0）— `openspec/changes/09-fat-rotate-iter3/tasks.md` T9.1/T9.4 已補閉；實作補拆 `src/cli/kb/fetch_commands.py`，使 `rebuild.py` 356→190、fetch_commands.py 176、_quality_gate_cli.py 145、_rebuild_corpus.py 89，全 ≤300；保留 `src.cli.kb.rebuild._run_fetcher_for_source` re-export 與 CLI app 註冊；驗證 `python -m pytest tests/test_kb_rebuild_cli.py tests/test_kb_gate_check_cli.py tests/test_cli_commands.py tests/test_fetchers.py -q -k "rebuild or gate_check or fetch_debates"` = 13 passed、`python scripts/sensor_refresh.py --human` red_over_400=[]。
> 3. ✅ **T-BARE-EXCEPT-AUDIT 刀 9**（10 處一刀清；49→39；797 passed）

> **v7.3–v7.7 sensor/header 歷史已封存**：詳見 [docs/archive/program-history-202604k.md](docs/archive/program-history-202604k.md)。

---

## P0 已全閉段（07:50 回顧）

### P0（2026-04-26 07:50 /pua 深度回顧新增；已全閉，保留追溯 — 治理斷層第八型 + fat 預先收尾 + T15.5 證據鏈入版）

- [x] **T-OPENSPEC-FLUSH-15-16-ARCHIVE**（2026-04-26 閉；P0；治理底線真閉環）— 已由 commit `f357830` 歸檔 15/16；`openspec/changes/` 僅剩 `archive/`；`openspec/changes/archive/` 含 `2026-04-26-15-pytest-runtime-regression-iter7` 與 `2026-04-26-16-regulation-doc-type-mapping`；0 active changes。
- [x] **T-WORKTREE-FLUSH-LOOP6**（2026-04-26 閉；P0；T15.5 證據鏈入版）— T15.5 證據鏈已由 commit `62b2d85` 入版（`pyproject.toml` `-n auto → -n 8` + `docs/pytest-runtime-regression-iter7.md` + tasks/program/results sync）；後續只剩 `.copilot-loop.state.json` tracked noise，另由 `T-COPILOT-LOOP-STATE-GITIGNORE` / `T-GIT-ACL-DENY-UNBLOCK` 追。
- [x] **T-FAT-PRE-EMPT-CUT-V2**（2026-04-26 閉；P0；ACL-free；防下輪炸 ≥400）— 已抽出 `src/knowledge/_manager_write.py`、`src/core/prompt_safety.py`、`src/web_preview/_history.py`、`src/cli/_wizard_generate.py`，保留舊 import/mixin/CLI 呼叫面；`manager.py 373→225`、`constants.py 367→297`、`web_preview/app.py 364→347`、`wizard_cmd.py 361→174`。驗收 `python scripts/check_fat_files.py --strict` = red=0/yellow=1/baseline count=1 max_lines=350；`python -m pytest tests/ -q --ignore=tests/integration` = 3958 passed / 195.10s。

---

## P0 已全閉段（05:55 + v7.9-final/sensor 歷史段）

### P0（2026-04-26 05:55 /pua 深度回顧新增；本輪必動 — 治理底線 + T15.5 紅線真閉環；已全閉，保留追溯）

- [x] **T-WORKTREE-FLUSH-LOOP5**（2026-04-26 閉；P0；ACL-free；治理底線）— 已 flush 13/14 openspec promote、`src/cli/utils.py` shim removal、`tests/test_cli_commands.py` xdist/state cleanup 與治理文件更新；驗證 `python -m pytest tests/ -q --ignore=tests/integration` = 3951 passed / 248.81s。剩餘活 spec 僅 `15-pytest-runtime-regression-iter7`；T15.5 因 runtime > 200s 仍未關。
- [x] **T15.5-MEDIAN-COLD-START**（2026-04-26 閉；P0；ACL-free；紅線 v9 真閉環）— 根因為 Windows NTFS/import I/O 被 xdist 14 workers 過飽和；`pyproject.toml` 將 pytest `addopts` 從 `-n auto` 改為 `-n 8`。驗證同 HEAD `4d105f5` 冷啟動雙跑（每次前清 `__pycache__` + `.pytest_cache`）：Gate C `3958 passed / 183.98s`、Gate D `3958 passed / 195.64s`，median **189.81s ≤ 200s**；詳見 `docs/pytest-runtime-regression-iter7.md`。
- [→merged] **T-OPENSPEC-PROMOTE-13-14-FLUSH**（P0；併入 T-WORKTREE-FLUSH-LOOP5 (a) 子任務；2026-04-26 05:55 升級）— 從上輪 P1 「partially done」直升 P0 並合併執行；不再分項拖。

### P0（v7.9-final 後段 /pua 深度回顧新增；漂白第七型 / 工作量黑洞 / 本輪必動）

- [x] **T-XDIST-RACE-AUDIT**（P0；30–45 min；ACL-free；漂白第七型 = 測試再現性）— sensor `--human` 報 0 hard violations / 3950 passed，但 `python -m pytest tests/ -q --ignore=tests/integration` -n auto 實測 **1 failed / 14 errors / 263.64s**；**2026-05-xx 閉：修復全 19 個 CI 失敗（HOME env、jieba dev-dep、xdist state leak、mix_stderr、e2e mock corpus 等），本機 3951 passed + 推送 CI 觸發驗收。**
- [x] **T-WORKTREE-FLUSH-LOOP4**（2026-04-26 閉；P0；ACL 已開）— 19 檔 196+/394- 工作樹已入版：(a) `refactor(core): T13.5 extract append_record to src/core/history_store`（c4d7ef4）；(b)+(c) `refactor(cli): T13.4 extract verify_service to src/cli/shared`（3e75832）；(e) `docs(archive): T-ENGINEER-LOG-PRE-ROTATE`（6327c6f）；共 3 語意 commit，全過 commit_msg_lint。驗收：`git status` clean（扣除 .copilot session）、3951 passed ✅。

### P0（v7.9-final 02:32 /pua 深度回顧新增；漂白第五型 / 公式漂白第六型 / 本輪必動）

- [x] **T-LITELLM-WARNING-CLOSE-V2**（P0；30 min；ACL-free；2026-04-26 閉）— integration `tests/integration/test_meeting_multi_round.py::test_meeting_two_requests_get_different_session_ids` 仍噴 4× `PydanticSerializationUnexpectedValue`；建立 `tests/integration/conftest.py` session-scope autouse 注入 `MockLLMProvider` 至 `src.api.dependencies._llm`；驗收：`GOV_AI_RUN_INTEGRATION=1 python -m pytest tests/integration -W error::UserWarning -q` = 17 passed / 0 UserWarning exit 0 ✅。
- [x] **T-SENSOR-RESCUE-EXCLUDE**（P0；10 min；ACL-free；公式誠實化；2026-04-26 閉）— sensor 公式補 reject `chore\(auto-engineer\):\s*AUTO-RESCUE` + `chore\(auto-engineer\):\s*\d+\s*files`；commit_msg_lint 同步；驗收：sensor `--human` `auto_commit_rate` 即時跌至 ≤ 25%。
- [x] **T-WORKTREE-COMMIT-FLUSH-MERGED**（2026-04-26 閉；P0）— ACL DENY 已由 Admin 解除；3 件語意 commit 入版；`git status` clean；T-WORKTREE-FLUSH-LOOP4 同步閉環 ✅。

### P0（v7.9-sensor 終段 01:05 /pua 深度回顧新增；治理斷層 / worktree 滯留 / cli 神物件）

- [→merged] **T-GITHUB-REMOTE-SETUP**（已併入 T-WORKTREE-COMMIT-FLUSH-MERGED）
- [→merged] **T-ACL-V3-HOST-VERIFY**（已併入 T-WORKTREE-COMMIT-FLUSH-MERGED）
- [→merged] **T-ACL-V2-VERIFY**（已併入 T-WORKTREE-COMMIT-FLUSH-MERGED）
- [→merged] **T-WORKTREE-COMMIT-FLUSH**（已併入 T-WORKTREE-COMMIT-FLUSH-MERGED）
- [x] **T-ACL-V3-RCA**（2026-04-26 閉；P0；handoff doc done / host action pending）— `docs/acl-v3-rca-handoff.md` 補：本輪重現證據、已試方法、stale lock/tmp 檢查點、host/Admin recovery order。
- [x] **T-COPILOT-NOISE-PATCH**（2026-04-26 00:18 閉；P0；ACL-free；待入版）— `chore(copilot): batch round` 漂白第四型在 `scripts/commit_msg_lint.py` 拒絕、`scripts/sensor_refresh.py` 排除語意率；驗證 41 passed ✅。
- [x] **T-FAT-PRE-EMPT-CUT**（2026-04-26 閉；P0；ACL-free）— `validators.py` 390→275 / `_execution.py` 389→208 / `law_fetcher.py` 377→296；ratchet 收緊；全量 3951 passed ✅。
