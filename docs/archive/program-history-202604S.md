# Program History Archive — 202604S

Archived from `program.md` on 2026-04-27 (T-PROGRAM-MD-SOFT-CAP-V8.15).
Contains: v8.10–v8.14 P0/P1/P2 completed task sections.

---

### P0（epic 20 — pytest-runtime-regression-guard；integration + tests 先行）

- [x] **T20.2-SENSOR-INTEGRATION**（P0；ACL-free；**integration-first**）— `scripts/sensor_refresh.py` 新增 `check_pytest_runtime(repo)` + `sensor["pytest_runtime"]` 欄位；讀 `scripts/pytest_runtime_baseline.json` last_s 對比 ceiling_s×(1+tolerance)；soft violation `"pytest-runtime-regression"`；missing baseline → `status:"skip"`；驗收：unit test 注入 ceiling×1.21 觸發 soft violation；sensor tests 全綠。**（T20.1 script 前置）**
- [x] **T20.3-UNIT-TESTS**（P0；ACL-free；**integration-first**）— `tests/test_pytest_runtime_guard.py` ≥6 tests（dry-run baseline / ratchet-down / no-ratchet-up / soft violation fire / status-ok / missing file skip）；全 mock 無 live pytest；驗收：`pytest tests/test_pytest_runtime_guard.py -q` all passed。
- [x] **T20.1-MEASURE-SCRIPT**（P0；ACL-free；T20.2 前置）— `scripts/measure_pytest_runtime.py` 建立：`--dry-run`（skip pytest，last_s=0.0）+ `--timeout`（預設 600s）+ write `scripts/pytest_runtime_baseline.json {ceiling_s, last_s, tolerance:0.20, measured_at}`；ratchet-down（ceiling 只降不升；首次 ceiling=last_s×1.5）；驗收：`python scripts/measure_pytest_runtime.py --dry-run` exits 0。
- [x] **T20.4-HUMAN-OUTPUT**（P1；ACL-free）— `sensor_refresh.py --human` markdown 輸出補 `pytest_runtime` section（ceiling_s / last_s / status table row）；驗收：`python scripts/sensor_refresh.py --human` includes `pytest_runtime`。
- [x] **T20.5-DOCS**（P2；ACL-free）— `CONTRIBUTING.md` 補 "Pytest Runtime Baseline" 節（`measure_pytest_runtime.py --dry-run` / `--timeout` 旗標 / ratchet-down semantics）；驗收：`grep -n "pytest_runtime" CONTRIBUTING.md` 命中。

### P0（2026-04-27 Copilot agent v8.13 — 維護批次：epic 19 封存 + log rotation + epic 20 開站）

- [x] **T-EPIC-19-ARCHIVE**（ACL-free；v8.13）— epic 19 (19-kb-recall-validation-pipeline/) `git rm` 後複製到 archive/2026-04-27-19-...；INDEX.md 補 epic 17 + 19 條目；sensor active_epic="" 驗收；37 sensor tests passed。
- [x] **T-ENGINEER-LOG-ROTATE-v11**（ACL-free；v8.13）— engineer-log.md 262→138 行；v8.3/v8.3-REVIEW/v8.4 反思 3 段（~124 行）封存 docs/archive/engineer-log-202604O.md；header 指標 202604O 補；sensor log_lines=138 驗收。
- [x] **T-OPENSPEC-EPIC-20-DISCOVERY**（ACL-free；v8.13）— openspec/changes/20-pytest-runtime-regression-guard/ 建立（.openspec.yaml + proposal.md + tasks.md）；sensor active_epic=20-pytest-runtime-regression-guard total=25；epic 20 任務：T20.1-T20.5 pytest 冷啟動回歸守衛。
- [x] **T-SENSOR-ZERO-ACTIVE**（ACL-free；v8.13）— sensor active_epic 空值優雅處理（epic_id=""，done=0，total=0）已由 T-EPIC-19-ARCHIVE 驗收；37 sensor tests passed。
- [x] **T-PROGRAM-MD-V8.13-HEADER**（ACL-free；v8.13）— program.md 加 v8.13 batch header；5 任務全 [x]；results.log 追加 5 行 PASS。

### P0（2026-04-27 Copilot agent v8.11 — epic 19 recall pipeline 閉環）

- [x] **T-EPIC-19-T19.3-RECALL-BASELINE**（ACL-free；v8.11）— `scripts/recall_baseline.py` 建立：`save_recall_baseline(model, recall_at_5, *, path, tolerance)` ratchet-down floor（floor 只降不升）+ `read_recall_baseline(model)`；預設路徑 `scripts/recall_baseline.json`；5 ratchet-semantics tests passed。
- [x] **T-EPIC-19-T19.4-SENSOR-INTEGRATION**（ACL-free；v8.11）— `scripts/sensor_refresh.py` 新增 `check_recall_health(repo)` + `recall_health` 欄位；讀 `recall_report.json` recall@5 對比 baseline floor；soft violation `"recall-degradation"` 當 recall@5 < floor*(1-tolerance)；37 sensor tests passed。
- [x] **T-EPIC-19-T19.5-UNIT-TESTS**（ACL-free；v8.11）— `tests/test_recall_eval.py` 12 tests：ratchet semantics 5 / sensor health 4 / recall computation 3；全 mock，無 live KB；`pytest tests/test_recall_eval.py -q` = 12 passed。
- [x] **T-EPIC-19-T19.6-CI-INTEGRATION**（ACL-free；v8.11）— `CONTRIBUTING.md` 補 live recall eval 說明；`openspec/changes/19-*/tasks.md` T19.4/T19.5/T19.6 全 [x]；`pytest tests/test_recall_eval.py tests/test_sensor_refresh.py -q` = 49 passed。

### P2（2026-04-27 Copilot agent v8.11 新增；program.md soft cap 治本）

- [x] **T-PROGRAM-MD-ARCHIVE-202604Q**（10 min；P2；ACL-free；v8.11 新增）— program.md 261 行 > soft 250；封存 v8.8/v8.6 P0/P1/P2 完成區塊（lines 48-135）到`docs/archive/program-history-202604Q.md`；主檔降至 < 200 行（< 250 ✅）；header pointer 補。

### P0（2026-04-28 Copilot agent v8.12 — sensor MDU fix + recall smoke + log hygiene）

- [x] **T-SENSOR-MDU-WINDOW-FIX**（ACL-free；v8.12）— `count_marked_done_uncommitted()` 掃描收窄至帶 ISO 日期的 P0/P1 section header；遇 `---` 或無日期 header 即停；hard violation 由 30 降至 1（soft only）；37 sensor tests passed。
- [x] **T-RECALL-DRY-RUN-SMOKE**（ACL-free；v8.12）— `python scripts/eval_recall.py --dry-run` 驗收：recall_report.json 建立，含 recall@1/3/5 / embedding_model / n_eval 欄位；exit 0。
- [x] **T-RESULTS-LOG-SOFT-CAP**（ACL-free；v8.12）— results.log 317 行 > soft 300；前 217 行封存 `results-archive/202604R.log`；主檔降至 100 行。
- [x] **T-SENSOR-JSON-COMMIT**（ACL-free；v8.12）— sensor.json 漂白 + 本輪所有修改一次 commit 落版；git status clean。
- [x] **T-PROGRAM-MD-V8.12-HEADER**（ACL-free；v8.12）— program.md 加 v8.12 batch header；5 個任務全 [x]。

> - ✅ **HEAD = origin/main = 6426ad7**（rev-list 0/0；v8.9 push flush 仍守）
> - ✅ **pytest -x = 4001 passed / 158.43s**（vs v8.8 80.43s 漲 +97%；soft 200s 守住）
> - ✅ **sensor 全綠真值**：bare=1 noqa / fat 0/0 / runtime cold 24.44s（v3 ceiling 100s+tolerance 0.2 真量測 ✓）
> - ✅ **openspec active=1 真值**（19-kb-recall-validation-pipeline；T19.1 [x] eval set 35 筆）
> - ⚠️ **漂白第一型 1 輪再生**：runtime_baseline.json (sensor side-effect 寫) + req.json/req-out.json 漂入 = v8.8 「4 輪終止」紀錄破
> - ⚠️ **epic 19 stall 1/6 = 16%**：T19.2-T19.6 5 子任務 [ ]；不推 = active=1 名義真實質凍結，第 7 輪 treadmill 預兆
> - ⚠️ **sensor.epic6_progress 死碼**：epic 6 已歸 archive 但欄位仍 done=0/total=0 = 漂白第二型口徑放水第二例
> - ⚠️ **fat watch 300-350 = 3 檔邊緣**：utils_io 306 / editor/flow 304 / web_preview/app 300

### P0（2026-04-26 23:32 /pua v8.10 深度回顧新增；本輪必動 — 漂白第一型 1 輪再生 + epic 19 stall）

- [x] **T-WORKTREE-FLUSH-V9.0**（15 min；P0；ACL-free；漂白第一型 1 輪即生治本）— (a) `.gitignore` 加 `req*.json` 排除小型 FastAPI smoke 殘檔；(b) `scripts/sensor_refresh.save_runtime_baseline` 改 hook-safe 寫 `~/.cache/gov-ai/runtime_baseline.json` 非版控（治本反模式）或 commit baseline 真值並 carve out white-list；(c) 1 語意 commit 落版（chore(state) 或 fix(sensor)）；驗收 `git status --short` clean。**不修 = sensor 每輪都產 dirty = 「sensor 寫工作樹 = 漂白第一型永動機」結構債**。owner=auto-engineer。
- [x] **T-EPIC-19-T19.2-EVAL-RECALL-IMPL**（45 min；P0；ACL-free；epic 19 推進治本 — 第 7 輪 treadmill 預警）— `scripts/eval_recall.py` 落地：load `kb_data/eval_set/recall_eval.jsonl`、call `knowledge_manager.search(q, k=5)`、計 recall@1/3/5、output `recall_report.json` schema `{embedding_model, recall@1, recall@3, recall@5, n_eval}`、`--dry-run` exit 0、`--k` 預設 5；新增 `tests/test_eval_recall.py` ≥5 cases（dry-run / k 旗標 / 空 jsonl 邊界 / search hit / search miss）；勾 `openspec/changes/19-*/tasks.md` T19.2 全部 sub-checkbox。驗收：`python scripts/eval_recall.py --dry-run` exit 0 + `tests/test_eval_recall.py` 5+ passed + targeted pytest 不退。

### P1（2026-04-26 23:32 /pua v8.10 新增；sensor 字段失準 + fat 3 檔邊緣同刀）

- [x] **T-SENSOR-ACTIVE-EPIC-PROGRESS**（20 min；P1；ACL-free；漂白第二型治本 — 口徑放水第二例）— `scripts/sensor_refresh.py` 把 `epic6_progress` 字段改名 `active_epic_progress`；解析 `openspec/changes/` 第一個非 `archive/` 目錄的 `tasks.md` 計 `[x]` / 總 `[ ]+[x]+[~]` 比例；多個 active 取首個並列名；補 `tests/test_sensor_refresh.py` 2 cases（active=0 fallback / active=1 統計）；驗收：sensor.json `active_epic_progress.epic_id == "19-kb-recall-validation-pipeline"` + `done/total` 動態真值。
- [x] **T-FAT-WATCH-CUT-V6**（30 min；P1；ACL-free；3 檔同模組同刀 ROI ×3）— `src/cli/utils_io.py 306→260`（抽 `_atomic_writes.py` ≥40 行 atomic_text/json/yaml_write 三家）+ `src/agents/editor/flow.py 304→260`（抽 `_safe_low_path.py` ≥40 行 score/refine 邏輯）+ `src/web_preview/app.py 300→255`（抽 `_health_routes.py` ≥40 行 health/static 路由）；驗收 `python scripts/check_fat_files.py --watch-band 300-350` ≤ 1 檔 + 全量 pytest 不退。

### P2（2026-04-26 23:32 /pua v8.10 新增；results.log 預治）

- [x] **T-RESULTS-LOG-ARCHIVE-202604P**（10 min；P2；ACL-free；soft 1000 紅線預治）— results.log 897 行接近 soft 1000；下輪寫前必先把 v8.7-v8.9 三輪 PASS/FAIL-BLOCKED 條目（line ~700-880）封存到 `results-archive/202604P.log`；主檔 ≤ 300 留下輪空間；header pointer 補。
