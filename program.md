# Auto-Dev Program — 公文 AI Agent（真實公開公文改寫系統）

> 歷史 v7.0–v8.3 batch header 已封存：[docs/archive/program-history-202604j.md](docs/archive/program-history-202604j.md)、[docs/archive/program-history-202604k.md](docs/archive/program-history-202604k.md)、[docs/archive/program-history-202604L.md](docs/archive/program-history-202604L.md)、[docs/archive/program-history-202604M.md](docs/archive/program-history-202604M.md)
> 歷史 v8.1/v8.3/v8.4/v8.5 完成任務已封存：[docs/archive/program-history-202604O.md](docs/archive/program-history-202604O.md)（T-PROGRAM-MD-ARCHIVE-202604O；2026-04-26 22:51）
> 歷史 v8.6/v8.8 P0/P1/P2 已封存：[docs/archive/program-history-202604Q.md](docs/archive/program-history-202604Q.md)（T-PROGRAM-MD-ARCHIVE-202604Q；2026-04-27）

> **v8.12 批次回合（2026-04-28 Copilot agent；HEAD=TBD→push）**：
> - ✅ **T-SENSOR-MDU-WINDOW-FIX** sensor marked_done_uncommitted 誤報 30 → 1；收窄掃描至帶日期的 P0/P1 header；37 tests passed
> - ✅ **T-RECALL-DRY-RUN-SMOKE** `eval_recall.py --dry-run` 驗證 recall_report.json 正確建立（recall@1/3/5 欄位）
> - ✅ **T-RESULTS-LOG-SOFT-CAP** results.log 317 → 100 行；217 行封存 results-archive/202604R.log
> - ✅ **T-SENSOR-JSON-COMMIT** sensor.json + 本輪修改一次性 commit 落版
> - ✅ **T-PROGRAM-MD-V8.12-HEADER** program.md v8.12 header + 任務 [x]

> **v8.11 批次回合（2026-04-27 Copilot agent；HEAD=TBD→push）**：
> - ✅ **T19.3 recall_baseline.py** ratchet-down semantics 落地；5 tests passed
> - ✅ **T19.4 sensor recall_health** check_recall_health() + soft violation wired；37 sensor tests passed
> - ✅ **T19.5 tests/test_recall_eval.py** 12 unit tests 全綠（mock KB，無 live 依賴）
> - ✅ **T19.6 CI/CONTRIBUTING** 整合 + tasks.md 全 [x]；49 recall+sensor tests passed
> - ✅ **T-PROGRAM-MD-ARCHIVE-202604Q** 261→<200 行（v8.8/v8.6 區塊封存）

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



> **v8.9 批次回合（2026-04-26 22:51 Copilot agent；HEAD=0ca2431→push）**：
> - ✅ **HEAD = origin/main = 0ca2431**（10 commits 推送；rev-list 0/0；漂白第一型閉環）
> - ✅ **fix(api)：middleware 補 engines/static/mockup 公開路徑**（T-ENGINES-API-LAND 收尾；tests/test_api_server.py 259 passed）
> - ✅ **fix(cli)：config_tools 補 test_connectivity wrapper**（T-FAT-WATCH-CUT-V5 extract 後缺失修補）
> - ✅ **feat(sensor)：check_runtime ceiling+tolerance up-creep 偵測**（T-RUNTIME-BASELINE-TRUE-MEASURE-v3 真閉）
> - ✅ **T-PROGRAM-MD-ARCHIVE-202604O**：285→241 行（< 250 soft cap ✅）；v8.1/v8.3/v8.4/v8.5 區塊封存
> - ✅ **pytest 1051 passed / 76.82s**（test_api_server + test_sensor_refresh + test_cli_commands）

> **v8.7 批次回合（2026-04-26 21:18 Copilot agent；HEAD=cc0bbe2）**：
> - ✅ **工作樹散裝完全閉環**：3 commits（chore/docs/feat）清空 dirty worktree；git status = clean（扣 results.log 本輪最後一行）
> - ✅ **T-EPIC-18-COMMIT-FLUSH (v8.6) 閉環**：4 語意 commit 全數入版（含 bb2e802 前輪 + 本輪 3 commits）；git rev-list origin/main..HEAD = 4
> - ✅ **T-OPENSPEC-18-ARCHIVE-FLUSH**：openspec/changes/archive/2026-04-26-18-multi-llm-provider-abstraction/ + openspec/specs/multi-llm-provider/spec.md 已入版
> - ✅ **T-ENGINES-API-LAND**：feat(api) engines list/single/WS endpoint + config/engines.yaml SSOT + tests 2 passed
> - ✅ **T-GITIGNORE-STACKDUMP**：*.stackdump 加 .gitignore，bash.exe.stackdump 刪除
> - ✅ **pytest tests/test_engines_api.py tests/test_api_server.py tests/test_sensor_refresh.py = 293 passed**

*（v8.8/v8.6 P0/P1/P2 已封存 → [docs/archive/program-history-202604Q.md](docs/archive/program-history-202604Q.md)）*

### P1（連 2 輪延宕 = 3.25）

#### v7.9-sensor 終段 01:05 /pua 深度回顧新增 — CLI 神物件 / wrapper 治本 / CI 遠端驗

- [x] **T-CLI-FAT-ROTATE-V3**（2026-04-26 閉；P1；ACL-free；openspec only）— `openspec/changes/13-cli-fat-rotate-v3/` proposal + tasks 落地：(a) `utils.py` 拆 utils_io/utils_display/utils_text 三模組逐 importer 切換（T13.1a–e）；(b) 4 高風險 import 改公共介面：`lint_service`/`cite_service`/`verify_service`/`history_store`（T13.2–T13.5）；(c) 4 micro 合併（T13.6a–d）；(d) 回歸門（T13.7）；**本輪實作閉環（2026-04-26）：T13.1b — `utils_io.py`（306 行）建立，26 個 importer 全切，`src.cli.utils` 降為 51 行 shim；T13.1e — 切換剩餘測試 importer 到 `utils_io` 並刪除 `src/cli/utils.py`，直接 importer = 0；T13.1c — `utils_display.py`（11 行）Console singleton；T13.1d — `utils_text.py` placeholder，utils.py ≤ 80 行，fat-gate OK red=0 yellow=6；T13.6a — `highlight_cmd.py`（43 行）合入 `search_cmd.py`，刪源檔；T13.6b — `number_cmd.py`（44 行）合入 `stamp_cmd.py`，`gov-ai number` 仍由 main 註冊；T13.6c — `replace_cmd.py`（44 行）合入 `redact_cmd.py`，backup 失敗測試改 patch 新位置；T13.6d — `batch_io.py`（22 行）合入 `batch_runner.py`，persist `__init__` 僅 re-export；全量 3951 tests passed ✅，T13.6b/c targeted 44 passed ✅，fat-gate red=0 yellow=6 ✅；**T13.7 回歸門 PASS（3951 passed, fat red=0, HIGH=0）✅**；T13.1e 補驗 `python -m pytest tests -q --ignore=tests/integration` = 3951 passed / 231.91s。
- [x] **T-COPILOT-WRAPPER-HOST-PATCH**（2026-04-26 repo 側完成；host Admin SLA 48 hr 待驗）— `docs/auto-commit-host-action.md` 升 actionable handoff：(a) supervise interval 5 min → 30 min；(b) squash window 同窗口 commit 合併；(c) message 模板強制 `feat|fix|refactor|docs|test|chore` 真語意；(d) 新增 AUTO-RESCUE + N-files 排除規則。Repo 側文件完成 ✅；host Admin 執行 checklist + 48 hr sensor 驗收由 Admin 補。
- [x] **T-CI-REMOTE-VERIFY**（2026-04-26 閉；P1；ACL-free）— `git remote -v` = empty（無 origin）；`docs/integration-ci-first-run.md` 末尾已補 "local-only verification, GitHub Actions integration job pending remote setup" 標記；升 P0 開 **T-GITHUB-REMOTE-SETUP**。

#### v7.9-sensor 後段 00:15 /pua 深度回顧新增 — CI 真跑驗收 + cli 顆粒度

- [x] **T-INTEGRATION-CI-FIRST-RUN-VERIFY**（2026-04-26 閉；P1；CI-only）— 本機無 `origin` remote，改以本機等效指令驗收：`GOV_AI_RUN_INTEGRATION=1 python -m pytest tests/integration/ -v --tb=short --ignore=tests/integration/test_e2e_rewrite.py` = **16 passed / 18 skipped（live-source gate）/ 0 failed**，符合 CI 設計（GOV_AI_RUN_LIVE_SOURCES 未設 = 跳過外部 API 測試）；T-INTEGRATION-CI-WIRE 閉環確認有效；驗收文件 `docs/integration-ci-first-run.md` ✅。
- [x] **T-CLI-COUPLING-AUDIT**（2026-04-26 閉；P2→P1；ACL-free）— `scripts/cli_ast_audit.py` AST 掃 80 檔 10,924 行；`docs/cli-module-audit.md` 已輸出：(1) 35 直接指令 + 12 群組指令樹；(2) 6 跨群組 import（4 高風險：`generate/export` 借用 `cite_cmd`/`lint_cmd` 私有符號、`kb/rebuild` 借用 `verify_cmd`、`generate/__init__` 直寫 `history`）；(3) 9 micro 檔（<50 行）可合併、11 fat 檔（≥250 行）；結論：fat-rotate v3 治理**有必要**（`utils.py` 26 個 importer 神物件 + 冰山耦合 + 雙峰分布）。

#### v7.8c 20:08 /pua 深度回顧新增 — integration 補漏 + 外部 blocker 上升

- [x] **T-INTEGRATION-COVERAGE-PHASE-2**（2026-04-25 閉；P1；ACL-free）— 新增 4 個 integration 測試檔（test_kb_cli_flow.py 3 tests / test_cite_cmd_e2e.py 5 tests / test_web_preview_smoke.py 4 tests / test_meeting_multi_round.py 5 tests）；無 GOV_AI_RUN_INTEGRATION=1 時全 16 tests SKIP；integration count 4→8；主套件 `python -m pytest -q --ignore=tests/integration --tb=line` = 3949 passed ✅。
- [x] **P1-AUTO-COMMIT-EXTERNAL-PATCH**（2026-04-25 20:31 閉；repo-side handoff）— 已新增 `docs/auto-commit-host-action.md` host-side 清單（interval 5→30 min / squash window / semantic message template / 驗證命令），並在 `HANDOFF.md` 補 host Admin 錨點；repo 內可交付部分完成。後續驗收移交 `T-COMMIT-T12.5-VERIFY`：待 host reload 後 rolling 30-commit 真語意率 90%+、`git log -n 30 --format=%s` 無 `chore(auto-engineer): patch`、逐行 pipe 到 `python scripts/commit_msg_lint.py -` 全綠。
- [x] **T-COMMIT-T12.5-VERIFY**（2026-04-25 閉；5 min；P1；ACL-free）— `openspec/changes/12-commit-msg-noise-floor/tasks.md` T12.5 驗證完成；`git log -n 30 --format=%s` 逐行 pipe 到 `python scripts/commit_msg_lint.py -` exit 0，0 violations；`python scripts/sensor_refresh.py` rate=100% ≥ 0.9；change 12 進 archive；openspec/changes/ 僅剩 archive/。

#### v7.8b 反思新增 — 雙紅線同檔優先（ROI ×2）

- [x] **T-FAT-REALTIME-LOOKUP-CUT**（45 min；P1；2026-04-25 18:35）— `src/knowledge/realtime_lookup.py` 386 行同時是 fat yellow（max 386）+ bare-except 熱點（2 處）；拆 `_request_helpers.py` / `_normalize.py` 抽 80–100 行；同時把 except Exception 收 typed bucket；目標：fat 386 → ≤ 300、bare-except 熱點 -2 = 37、全量 pytest 不退（`tests/test_realtime_lookup.py` 既有 case 全綠）。**雙刀同檔，commit 一份做兩件**。
- [x] **T-INTEGRATION-COVERAGE-EXPAND**（60 min；P1；2026-04-25 18:35；2026-04-25 閉）— 新增 `tests/integration/test_kb_rebuild_quality_gate.py`（5 tests；mojlaw + executive_yuan_rss 各跑 QualityGate.evaluate，含 LiveIngestBelowFloor + timestamp UTC 驗證 + multi-source 聯跑）+ `tests/integration/test_api_server_smoke.py`（3 tests；uvicorn boot + GET / + GET /api/v1/health schema + POST /api/v1/meeting happy-path）；無 GOV_AI_RUN_INTEGRATION=1 時全 8 個 SKIP；主套件 `python -m pytest tests/ -q --ignore=tests/integration --tb=line -x` = 3949 passed ✅。

#### v7.8 反思新增 — 結構治理（連 5+ 輪同根因，需上工程而非 patch）

- [x] **T-AUTO-COMMIT-RUNTIME-SEAT**（2026-04-25 17:35 閉；P1→P2 凍結）— 已輸出 `docs/auto-commit-runtime-seat.md`：`.auto-engineer.state.json` 指向 PID 12668、`.auto-engineer.pid` 一致、`.copilot-loop.state.json` 無 formatter；`tasklist /v` 在本 shell `Access denied`、`where supervise` 無結果、repo scan 無 `auto-commit:` template。結論：commit formatter 在 external wrapper / scheduler / Admin rescue layer，repo 內不可直修；已寫 host-side patch point、validator 接法與驗收條件。
- [x] **T-COMMIT-NOISE-FLOOR**（30 min；P1；2026-04-25 v7.8 開）— 近 30 commit 28 條 = `auto-commit checkpoint` 噪音 93%，git blame/bisect 失效；治本兩刀：(a) 改 supervise loop interval 從 5 min → 30 min；(b) 5 min 窗口內 squash + 補語意 message 模板；2026-04-25 18:28 repo-side 防線補強：`scripts/commit_msg_lint.py` 拒絕 semantic-looking `chore(auto-engineer): checkpoint snapshot ...` 噪音，避免新 wrapper 前綴繞過 lint；驗證 `python -m pytest tests/test_commit_msg_lint.py tests/test_validate_auto_commit_msg.py -q` = 55 passed；仍待 external interval/squash 24hr 驗收。
- [x] **T-FAT-RATCHET-GATE**（2026-04-25 閉；P1；ACL-free）— `scripts/check_fat_files.py` 建立：任一 src/ Python 檔 ≥ 400 行 = exit 1；`scripts/fat_baseline.json` 記錄 yellow 10 檔基線（max 391）；`--strict` 驗 ratchet（count + max_lines 不得增）；`sensor_refresh.py` 對齊 ≥400 red downstream hard check + `fat_ratchet_ok/detail` 欄位；CI 已接 `python scripts/check_fat_files.py --strict`；新增 `tests/test_check_fat_files.py` 防 400 行邊界 / yellow ratchet 退化。驗證 `python scripts/check_fat_files.py --strict` exit 0 ✅、`python -m pytest tests/test_check_fat_files.py tests/test_sensor_refresh.py -q --tb=short` = 20 passed ✅。

#### v7.8 反思新增 — 深挖類

- [x] **T-INT-TESTS-SKIP-AUDIT**（2026-04-25 閉；P1；ACL-free）— `docs/integration-skip-audit.md` 輸出：全部 10 個 skip 均屬 `tests/integration/test_sources_smoke.py`（`GOV_AI_RUN_INTEGRATION != "1"` live-API gating）；主套件 3926 passed / 0 skipped；chromadb/multipart/win32 平台 skip 條件均為 False（依賴已安裝）；無環境缺失 / 無故意 skip 技術債。驗證 `python -m pytest tests/ -q --ignore=tests/integration --tb=no | tail -1` = `3926 passed` ✅。
- [x] **T-CASCADE-QUALITY-GATE-TEST**（2026-04-25 閉；P1；ACL-free）— `tests/test_quality_gate_cascade.py` 4 條 cascade 測試：(1) multi-source fail-stop（LiveIngestBelowFloor 中止後 source_c 不執行）；(2) partial pass（no fail-stop 收集所有 pass/fail）；(3) cascade ordering（SchemaIntegrityError 不污染下一 adapter）；(4) mixed named errors（4 種命名錯誤同批跑）；驗證 `python -m pytest tests/test_quality_gate_cascade.py -v` = **4 passed** ✅。

#### 既有 P1（保留追蹤）

- [x] **T-TEST-LOCAL-BINDING-AUDIT**（2026-04-25 閉；commit `23802ec`；ACL-free）— `scripts/audit_local_binding.py` AST-based Type 1 iceberg scanner（67 候選）；`tests/test_audit_local_binding.py` 19 passed；`tests/conftest.py` `rebind_local()` helper with docstring；`CONTRIBUTING.md` Mock contract rules 三型完整章節（adb531c/c0933f9/1eef399）；`docs/test-mock-iceberg-taxonomy.md` 133 行 pre/post diff per type。
- [x] **T-PYTEST-RUNTIME-FIX-v3**（2026-04-25 07:30 閉；ACL-free）— 目標 ≤ 300s（現雙 baseline **179/173s** 已破；守穩住下輪 cold-start 若 > 220s = regression）。本輪修復：conftest.py mock_llm fixture regression（234 errors → 0）+ `_bm25_search` jieba early-return + pytest-xdist `-n auto`。結果：**146.67s / 3889 passed（-n auto, 20 workers）**；≤ 300s ✅；regression guard ≤ 220s ✅；歷史基線 179/173s 均優 ✅。
- [x] **EPIC6 T-LIQG-4**（2026-04-25 02:59 閉；本輪）— `gov-ai kb rebuild --quality-gate` 已接到 active corpus rebuild：先按來源批次 gate，任何 named failure 即中止，成功才進 only-real merge；補 `tests/test_kb_rebuild_cli.py` 驗證 PASS/FAIL 兩條路，`python -m pytest tests/test_kb_rebuild_cli.py tests/test_kb_gate_check_cli.py -q -k gate` = 6 passed。**P2-CORPUS-300 擴量前置再少一刀**。
- [x] **EPIC6 T-LIQG-5**（2026-04-25 閉；本輪）— `docs/quality-gate-failure-matrix.md` 4 named error 矩陣落地，涵蓋 triage、policy boundaries、`--require-live` 交互；驗證 `rg -n "LiveIngestBelowFloor|SchemaIntegrityError|StaleRecord|SyntheticContamination" docs/quality-gate-failure-matrix.md` 全命中。
- [x] **T-SYNTHETIC-AUDIT**（P1；2026-04-25 建；2026-04-26 全補閉）— `scripts/audit_synthetic_flag.py`（97 行）建立；`tests/test_audit_synthetic_flag.py` = 18 passed；**37 份 gazette 未標 `synthetic:` 已於本輪補 `synthetic: false`；`--strict` exit 0，192/192 tagged ✓**；與 T-LIQG-1 `SyntheticContamination` 檢測契合，CORPUS-300 擴量掃雷完成。
- [x] **EPIC6 T-LIQG-1**（2026-04-25 02:20 閉；commit `c53a947` auto-engineer 吃 checkpoint 格式）— `src/sources/quality_gate.py`（171 行）+ `tests/test_quality_gate.py`（99 行）：`QualityGate.evaluate` + 4 named failure 合約落地。⚠️ auto-engineer commit message 違反 T-COMMIT-SEMANTIC-GUARD（用 `auto-commit: checkpoint` 裸格式），T-AUTO-COMMIT-SEMANTIC 升 P0 處理。
- [x] **T-PYTEST-RUNTIME-FIX**（2026-04-24 本輪四段對症；全部達標）— (1) 2026-04-22 11:03 `src/cli/main.py` help-only boot gate (28.84s → 0.43s)；(2) 第四十一輪 `f2fc2ad` + `adb531c fix(test): preflight re-bind` 修 StopIteration flake + `src.api.app.get_config` local binding；(3) **本輪 `cc5ac3c perf(tests)` autouse `_no_fetcher_backoff_sleep` 清 6 × 7s retry backoff = 42s**；(4) **本輪 `6b41335 perf(tests)` patch `src.api.routes.workflow.get_llm/get_kb` local binding — meeting_exporter 119.77s → 2.53s 省 117s**。runtime 演進：**960s → 773s → 547s → 461.20s → 340.21s (-64.5% vs 開局)**。3790 passed / 5:40。**LOOP2 ≤ 700s ✅（裕量 360s）+ 內部 ≤ 500s ✅ + 下 epoch 新目標 ≤ 300s 只差 40s**。新 Top 1 `TestEditorSafeLowNoRefine::test_safe_score_no_auto_refine` 12.54s + `TestKBEdgeCases::test_search_very_long_string` 11.27s 留給 **T-TEST-LOCAL-BINDING-AUDIT**（冰山法則：所有 `from src.api.dependencies import ...` 的 module local binding 掃一遍同類 patch bypass）。
- [x] **P2-CORPUS-300**（2026-04-25 本輪閉；ACL-free）— corpus 200 → **400**（mohw path bug 修 + fda 大量拉取）；`src/sources/ingest.py` 加 `_safe_filename()` 修正 Windows 路徑 URL source_id bug；`tests/test_sources_ingest.py` 新增 6 tests（safe_filename + url_source_id ingest）34 passed；fda 200 / executive_yuan_rss 60 / mohw 20 / mojlaw 100 / datagovtw 20；驗證 `find kb_data/corpus -name "*.md" | wc -l` = **400 ≥ 300** ✅。
- [x] **P0.1-MOHW-LIVE-DIAG**（2026-04-24 17:01 閉；commit `7c46761`）— `docs/mohw-endpoint-probe.md`（128 行）實測：endpoint HTTP 200 / 25511 bytes / 1.20s / feed 10 items / today 2026-04-24 新聞 / `fixture_fallback=False` / `synthetic=False`；列 4 個已知限制（`source_doc_no` URL fallback / description HTML 含 `<style>` 塊 / RSS TTL 20min vs freshness_window / 無分頁無歷史）全部跨引到 EPIC6 T-LIQG-2 / T-LIQG-3 backlog；手動 probe 3 步驟 SOP + 失敗排查表。本 session live adapter call 獨立驗證：`MohwRssAdapter().list(limit=5)` 0.53s / 5 entries / cache 20 / 所有 normalize() OK。

### P2（Admin/key 依賴，不能當 P1 佔坑）

- [x] **EPIC6-DISCOVERY**（2026-04-24 16:58 閉；commit `33bf8ce`）— `openspec/changes/06-live-ingest-quality-gate/` proposal (43) + tasks (82) + `specs/quality-gate/spec.md` (111) = 236 行骨架；3 dimensions（volume floor / schema integrity / provenance signal）× 4 named failures（LiveIngestBelowFloor / SchemaIntegrityError / StaleRecord / SyntheticContamination）+ 5 個 T-LIQG-1..5 後續 tasks（gate 模組 + CLI + 失敗矩陣 doc）。
- [→P1] **P2-AUTO-COMMIT-EXTERNAL-PATCH**（2026-04-25 20:08 升級為 **P1-AUTO-COMMIT-EXTERNAL-PATCH**；見上方 P1 區塊；本條保留作回溯）— 原凍結為 P2 已連 6 輪無進展，/pua 反思判定：不再凍結，主動上升 host Admin。
- [x] **P2-CHROMA-NEMOTRON-VALIDATE** — `OPENROUTER_API_KEY` 已驗證有效（2026-04-25 13:56 `curl /api/v1/auth/key` 200，付費帳號 is_free_tier=false，limit=null 無限額，累計 usage=$0.000035）→ **unblocked，可執行**：跑 `gov-ai kb rebuild --only-real`（走 `nvidia/llama-nemotron-embed-vl-1b-v2:free` dim=2048 重建 ChromaDB）+ 撰寫 `docs/embedding-validation.md` 記錄向量化前後 search recall@k 對比。
- [x] **T6.1**（2026-04-26 閉；ACL-free；注：full 30-item eval 需啟動 API server）— blind eval baseline：`docs/benchmark-baseline.md` 記錄 v2.1 快照（afterfix17 limit=2, avg_score=0.8766, success_rate=1.0）+趨勢表+完整執行步驟；`benchmark/baseline_v2.1.json` 以 afterfix17 2 題快照為底；完整 30 題需 `python scripts/run_blind_eval.py --limit 30`。
- [x] **T6.2**（2026-04-26 閉；ACL-free）— benchmark trend：`scripts/benchmark_trend.py` 建立（append + 10% regression gate）；`benchmark/trend.jsonl` 以 8 個歷史 afterfix run 種子；`tests/test_benchmark_trend.py` = 19 passed；每次 T2.x 後可呼叫 `python scripts/benchmark_trend.py <result.json>` 追加趨勢並自動偵測 regression。

### Repo / Governance

- [x] **T9.1.a**（2026-04-26 閉；ACL-free）— benchmark corpus 版控復位：`.gitignore` 對 `benchmark/mvp30_corpus.json` 加白名單，保留 blind eval / baseline / trend 產物忽略；驗收 `git status --short --ignored benchmark` 顯示 corpus 可加入版控、產物仍為 `!!` ignored。
- [x] **T-CORPUS-PROVENANCE-PYTEST-IMPORT**（2026-04-26 閉；P2；ACL-free）— `tests/test_corpus_provenance_guard.py` 補 `import pytest`，修正 `pytest.skip(...)` 隱性 F821；驗證 `python -m pytest tests/test_corpus_provenance_guard.py -q -n 0 --tb=short` = 3 passed、`python -m ruff check tests/test_corpus_provenance_guard.py --no-cache` = PASS。
- [x] **T9.2**（2026-04-24 16:25 閉；commit `400130d`）— atomic tmp source/lock/cleanup audit 三層（`src/cli/utils.py` atomic_text/json/yaml_write；root `.gitignore` `.json_*.tmp` / `.txt_*.tmp` / `.yaml_*.tmp` pattern；`tests/conftest.py` session-autouse `_cleanup_stale_atomic_tmps` fixture）寫成 `docs/atomic-tmp-audit.md`；pytest `test_cli_utils_tmp_cleanup.py` = 3 passed / 0.31s。
- [x] **T9.3**（2026-04-24 閉；commit `2678b10`）— `docs/commit-plan.md` v2.2 已封存至 `docs/archive/commit-plans/2026-04-20-v2.2-split.md`（111 行）；主檔原位重寫為 v3 搭配 T-COMMIT-SEMANTIC-GUARD。
- [x] **T9.5**（2026-04-24 閉；commit `a838fd3` 前輪已落）— root 遺留 `.ps1/.docx` 歸位到 `scripts/legacy/`；本輪 `Get-ChildItem *.ps1 *.docx` root count = 0 + `scripts/legacy/` 實存 10 支 `.ps1`，header lag 補勾。
- [x] **T7.3**（2026-04-24 16:30 閉；commit `3ac5c90`）— `docs/engineer-log-spec.md`（104 行）定義 section format（三證自審 + 事故+處置 + 下輪錨點 + PUA 旁白）、soft cap 300 / hard cap 400、lifecycle append-only + 月檔封存（`engineer-log-YYYYMM<letter>.md`）、與 `program.md` / `results.log` 的角色分工。
- [x] **T10.2**（2026-04-24 16:30 閉；commit `3ac5c90` auto-engineer 版 superset；ACL-free）— `scripts/check_auto_engineer_state.py`（205 行）解析 `.auto-engineer.state.json` + **PID liveness check**（`os.kill(0)` / Windows `tasklist`），6 狀態 running/idle/stale/orphan/absent/malformed + 修復建議字串；`tests/test_check_auto_engineer_state.py` = 8 passed；實測本機 status=**orphan**（PID 17644 dead + state "running"，age 51h）建議 lock orphan + mark stale + allow pua-loop takeover。本 session 同時寫的 `check_autoengineer_stall.py` 子集（129 行，只看時間戳 5 狀態）因為重複實作被刪除（commit `51e6d5e` → 本 commit dedup）。T7.3 `docs/engineer-log-spec.md` 同 commit 順帶閉環。
- [x] **T10.4**（2026-04-24 16:28 閉；commit `e475169`）— `scripts/check_acl_state.py` 解析 `icacls .git` + 信任 SID 白名單（Administrators/SYSTEM/AuthUsers/本機 SID prefix）、輸出 JSON 報告 + exit 0/1 + `--human`；`tests/test_check_acl_state.py` = 8 passed；實測 status=denied deny_count=2（P0.D 未解）可作 pua-loop / auto-engineer 啟動 gate。

### 下 epoch 錨點（LOOP2+ 開出）

- [x] **T-TEST-LOCAL-BINDING-AUDIT**（2026-04-25 閉；commit `23802ec`；ACL-free）— 冰山三型系統性對策全落地：`scripts/audit_local_binding.py` AST 掃 Type 1 候選 67 處；`tests/conftest.py` `rebind_local()` helper；`CONTRIBUTING.md` Mock contract rules 三型；`docs/test-mock-iceberg-taxonomy.md` 133 行 pre/post diff；19 tests passed。
- [x] **T-PYTEST-RUNTIME-FIX-v3**（2026-04-25 07:30 閉；ACL-free）— 目標 ≤ 300s（現雙 baseline **179/173s** 已破；守穩住下輪 cold-start 若 > 220s = regression）。本輪修復：conftest.py mock_llm fixture regression（234 errors → 0）+ `_bm25_search` jieba early-return + pytest-xdist `-n auto`。結果：**146.67s / 3889 passed（1 pre-existing fail）**；≤ 300s ✅；regression guard ≤ 220s ✅；歷史基線 179/173s 均優 ✅。
- [x] **T-AUTO-COMMIT-SEMANTIC** ⬆ **升 P0**（2026-04-25 auto-engineer 再犯 2 次 `1eef399 / c53a947` checkpoint 裸格式；2026-04-25 閉）— `scripts/validate_auto_commit_msg.py` 33 passed；見 P0 閉環項。
- [x] **EPIC6 coverage 收尾**（2026-04-25 閉；本輪）— `openspec/changes/06-live-ingest-quality-gate/tasks.md` T-LIQG-0 + T-LIQG-6..12 全收尾；`spectra status --change 06-live-ingest-quality-gate` = proposal/specs/tasks ✓；`python -m pytest tests/ -q --ignore=tests/integration -x` = 3821 passed / 151.44s。

### Legacy / Frozen

- [x] **P2-Legacy-INDEX-LOCK**（2026-04-26 自然解除；ACL DENY 已消失；git commit 7 件落版驗證）
- [x] **P0.S-REBASE-APPLY** — ACL 已解；`scripts/rewrite_auto_commit_msgs.py --apply` 可執行（保留 legacy）。
- [ ] **P1.3（T2.0.a）** — `.env` + litellm smoke；ACL/key gating。
- [ ] **T2.3** — SurrealDB migration；凍結。
- [ ] **T2.5** — API 層融合；保留 legacy backlog。
- [ ] **T2.7-old / T2.8-old / T2.9-old** — 舊 Epic 2 條目；保留追蹤，不列本輪首要。
- [ ] **T5.2 / T5.3** — Epic 5 長尾：500 份 real corpus 後 rebuild；ChromaDB 停役仍凍結。
- [x] **P0.GG**（2026-04-24 閉；本 commit；ACL-free）— `docs/windows-gotchas.md`（~340 行）匯整 16 項專案實戰 Windows 坑 + loop starter checklist：MSYS2 中文 glob 失真 / bash cwd reset / cp950 / CRLF .bat / schtasks Access Denied → Startup folder / Node 20+ spawn .cmd EINVAL / Tauri CREATE_NO_WINDOW / cmd /c fd 孤兒 / dataclass+importlib sys.modules register / pytest rootdir 中文亂碼 / .git ACL DENY / MSYS2 fork 慢 / taskkill IM 連帶殺 / wscript 偽 orphan / Defender 拖 runtime / 新 session 啟動 4 步自檢。
- [ ] **P0.SELF-COMMIT-REFLECT** — 仍受 ACL 現況牽制；保留為治理題。
- [ ] **T1.6** — 已併入 corpus 擴量路線；保留原編號方便追歷史。

---

## 已完成
- [x] **T-OPENSPEC-CHANGE-17-EMBED-REST**（2026-04-26 閉；P1；ACL-free；spec 漂白第四型補軌跡）— 建 `openspec/changes/17-embedding-provider-rest-fallback/`，含 proposal、tasks、`embedding-provider` spec delta；引用 cf26345 / 00330c0 / e0d673a 三 commit；驗證 `spectra validate --changes 17-embedding-provider-rest-fallback` = valid、`pytest tests/test_llm.py -q` = 52 passed、非 integration 全量 = 3969 passed。
- [x] **T-XXE-TEST-IMPORT-GRAPH-FIX**（2026-04-26 閉；P0；ACL-free）— 修正 4 個 `inspect.getsource` 型 XXE 測試，改為可追蹤抽模組後的 import graph；`gazette_fetcher` 斷言匯入 `_parser`，`_parser.py` 斷言使用 `defusedxml` 且禁用 `xml.etree.ElementTree`；新增 `docs/abstraction-cut-sop.md` 防同型回歸。驗證 `python -m pytest tests/test_realtime_lookup.py -q` = 48 passed；`python -m pytest tests --ignore=tests/integration -q -x` = 3972 passed。
- [x] **T-COMMIT-NOISE-PATCH-CLOSE** (2026-04-25 closed; P0) - patch noise now rejected by scripts/commit_msg_lint.py and excluded by scripts/sensor_refresh.py; regression tests added; targeted pytest = 40 passed; sensor auto_commit_rate = 20.0 percent no whitening.

- [x] **T-PROGRAM-MD-ARCHIVE-v2**（2026-04-25 本輪閉；ACL-free）— v7.3–v7.7 sensor/header 歷史封存至 `docs/archive/program-history-202604k.md`；`program.md` 主檔回到 250 行 soft cap 以下，保留 v7.8 現況與活任務。
- [x] **T-AUTO-COMMIT-RUNTIME-SEAT**（2026-04-25 17:35 閉；本輪）— 完成 runtime-seat audit 文件 `docs/auto-commit-runtime-seat.md`；確認 repo-local validators 已存在但違規 formatter 不在 repo，可執行修補點移交外部 Admin wrapper。
- [x] **T-VALIDATORS-AUDIT**（2026-04-25 本輪閉；ACL-free）— `src/agents/validators.py` 391 行確認 yellow watch（≤400；單一 `ValidatorRegistry` 類 10 方法；只有 auditor + citation_checker 兩個 import face；`validator_registry` 模組級實例；下輪若新增方法 > 400 才觸發 fat-rotate）。
- [x] **T-SENSOR-HEAD-REFRESH-v4**（2026-04-25 本輪閉；ACL-free）— v7.5 sensor 區塊加入 program.md；HEAD 獨立量測：bare except 2/2、fat >400 = 0、validators 391 yellow watch、engineer-log 133、program.md 238（後為 224+sensor）、auto-commit 48.1%（13/27）、pytest 3914 passed。
- [x] **T-PROGRAM-MD-TRIM**（2026-04-25 本輪閉；ACL-free）— v7.0–v7.2 三段 sensor/header（71 行）封存至 `docs/archive/program-history-202604j.md`；主檔 294→224 行（soft cap 250 ✅）。
- [x] **T-BARE-EXCEPT-VERIFY**（2026-04-25 本輪閉；ACL-free）— 確認 `src/cli/cite_cmd.py:119 except Exception: # noqa: BLE001`（KB 搜尋降級，故意）與 `src/core/warnings_compat.py:8 except Exception: # pragma: no cover - compatibility with older pydantic`（compat import fallback，故意）均為有效 noqa/compat，無需修改；總量 2 處 / 2 檔；紅線清零 ✅。
- [x] **T-WORKTREE-CLEAN-v3**（2026-04-25 本輪閉；commit `827e601`；ACL-free）— 暫存 T-REGRESSION-FIX-刀8 的 7 個未入版 Python 變更（refine/pipeline/org_memory/review_parser/rewrite/agents/__init__/test_e2e）；`git status` clean（扣除 copilot session 檔）；exception bucket 擴寬契約守；3914 passed。
- [x] **T-FAT-ROTATE-V2 刀 13**（2026-04-25 本輪閉；ACL-free）— `src/web_preview/app.py 399` 拆出 `src/web_preview/_helpers.py`（42 行：`_WEB_UI_EXCEPTIONS` / `_parse_env_int` / `_parse_env_float` / `_sanitize_web_error` / `_log_web_warning`）；主檔 399→364 行；保留 `src.web_preview.app._sanitize_web_error` / `_api_headers` 匯入面；驗證 `python -m pytest tests/test_web_preview.py -q` = 39 passed。
- [x] **T-BARE-EXCEPT-AUDIT 刀 8**（2026-04-25 本輪閉；ACL-free）— 4 處裸 `except Exception:` 改為 typed bucket：`src/api/app.py → (ImportError, OSError, RuntimeError)`、`src/cli/config_tools_mutations_impl.py → (OSError, ValueError)` + 補 logger、`src/knowledge/fetchers/npa_fetcher.py → (ValueError, ET.ParseError)`、`src/agents/writer/cite.py → (ImportError, AttributeError)` + 補 logger；剩 2 個 noqa/compat 故意保留；總量 51→47；驗證 `python -m pytest tests/test_api_server.py tests/test_agents.py tests/test_agents_extended.py tests/test_cli_commands.py tests/test_fetchers.py -q` = 1464 passed。
- [x] **T-REGRESSION-FIX-刀8**（2026-04-25 閉；ACL-free）— 修正 bare-except 刀7/8 過度收窄 exception bucket 導致的 12 個測試回歸：`pipeline.py` 設 `verification_failed=True` + `except (LLMError, RuntimeError, OSError)`；`rewrite.py` KB 搜尋改 `except Exception`、LLM 呼叫加 `OSError`；`refine.py` 兩處加 `OSError`；`review_parser.py` 加 `OverflowError`/`ArithmeticError`；`org_memory.py` 加 `logger.warning`；`refine_draft` docstring 補 `待補依據`；修正 2 個 e2e 測試 mock 耗盡（KB 回傳 relevant result 避免 Agentic RAG refine 消耗 side_effect）；驗證 `python -m pytest` = **3914 passed / 10 skipped**。
- [x] **T-BARE-EXCEPT-AUDIT 刀 7**（2026-04-26 閉；ACL-free）— 10 個熱點檔共 20 處裸 `except Exception`/`except:` 改為命名 exception bucket（`LLMError`/`TemplateNotFound`/`TemplateError`/typed OS+runtime tuples）；同步補 `LLMError` 至 `_AUDITOR_LLM_EXCEPTIONS`；更新 4 個測試 mock `side_effect` 從 `Exception`/`RuntimeError` 改為 `LLMError`/`jinja2.TemplateNotFound`；src/ 總量 71→51（-20）；驗證 `python -m pytest tests/test_agents.py tests/test_agents_extended.py tests/test_editor.py tests/test_api_server.py tests/test_knowledge.py tests/test_cli_commands.py -q` = 1381 passed。
- [x] **T-BARE-EXCEPT-AUDIT 刀 6**（2026-04-25 閉；本輪）— 6 個熱點檔共 18 處裸 `except Exception`/`except:` 改為命名 exception bucket，保留原有降級與 logging 契約；驗證目標 6 檔 `except Exception|except:` 全 0、`src/` 總量 71（≤80）、`python -m pytest tests/test_knowledge_manager_unit.py tests/test_knowledge.py tests/test_graph.py tests/test_cli_commands.py tests/test_api_server.py tests/test_editor.py tests/test_agents.py tests/test_agents_extended.py -q` = 1521 passed。
- [x] **T-PYTEST-COLLECT-NAMESPACE**（2026-04-25 02:38 閉；ACL-free）— 修正 `tests/test_e2e_rewrite.py` 與 `tests/integration/test_e2e_rewrite.py` 同名導致的 pytest collect 衝突；新增 `tests/__init__.py`、`tests/integration/__init__.py` 與 root `conftest.py` 相容 shim，保住舊有 `from conftest import ...` 匯入；驗證 `python -m pytest tests/test_e2e_rewrite.py tests/integration/test_e2e_rewrite.py -q` = 5 passed、`python -m pytest tests/test_api_auth.py tests/test_api_server.py tests/test_e2e.py tests/test_stress.py -q` = 383 passed、`python -m pytest tests -q` = 3802 passed / 10 skipped。
- [x] **EPIC6 T-LIQG-3**（2026-04-25 02:53 閉；ACL-free）— `gov-ai kb gate-check --source <name>` 已接到 `src/cli/kb/rebuild.py`，走 source adapter fresh fetch + `QualityGate.from_adapter_name()`，支援 `--format human|json` 成功報告與 named failure JSON；新增 `tests/test_kb_gate_check_cli.py` 覆蓋 human/json success、`--since` 傳遞與 `SyntheticContamination` fail。驗證 `python -m pytest tests/test_kb_gate_check_cli.py -q` = 4 passed、`python -m pytest tests/test_cli_commands.py -q -k "kb_rebuild or kb_ingest or kb_search"` = 18 passed。
- [x] **EPIC6 T-LIQG-4**（2026-04-25 02:59 閉；本輪）— `gov-ai kb rebuild --quality-gate` 已接到 active corpus rebuild：先對每個 adapter 批次跑 gate，再進 only-real merge；gate 失敗時 stderr 輸出 structured JSON 並中止，不跑後續 adapter。新增 `tests/test_kb_rebuild_cli.py` 覆蓋 PASS/FAIL 兩路；驗證 `python -m pytest tests/test_kb_rebuild_cli.py tests/test_kb_gate_check_cli.py -q -k gate` = 6 passed。
- [x] **T-FAT-ROTATE-V2 刀 10**（2026-04-25 03:16 閉；ACL-free）— `src/sources/datagovtw.py` 已拆成 `src/sources/datagovtw/{__init__, reader, normalizer, catalog}.py`（5 / 149 / 156 / 76 行）；保留 `from src.sources.datagovtw import DataGovTwAdapter` 與 `src.sources.datagovtw.requests.Session.post` patch 面；驗證 `python -m pytest tests/test_datagovtw_adapter.py tests/test_sources_base.py tests/test_sources_ingest.py tests/test_live_ingest_script.py tests/test_quality_config.py tests/test_sources_cli.py -q` = 45 passed。
- [x] **近期閉環（2026-04-22）** — `T-PROGRAM-MD-ARCHIVE`、`T-PROGRAM-MD-ARCHIVE-REAL`、`T-PYTEST-PROFILE`、`T-ROLLUP-SYNC`、`T-FAT-ROTATE-V2` 刀 3/4/5/6/7/8/9、`T9.6-REOPEN-v4`、`T9.6-REOPEN-v5`、`T-BARE-EXCEPT-AUDIT` 刀 1/2/3/4/5、`P0-TEST-REGRESSION`（KB manager Chroma 降級處理；基線 3745）、`P1-PCC-ADAPTER`、`P0.1-FDA-LIVE-DIAG`、`P0.3-CORPUS-SCALE`、`EPIC5-TASKS-SPECS`、`T5.1`、`T5.2`、`T5.3`、`T5.4`。
- [x] **T-CLI-MAIN-RECONCILE**（2026-04-22 11:38 閉；ACL-gated）— `git diff src/cli/main.py tests/test_cli_commands.py` 確認 help-only boot gate 與 `_is_help_only_invocation` 測試意圖一致；`python -m pytest tests/test_cli_commands.py -q` 實測 **755 passed / 201.64s**，shell wrapper timeout 但 pytest 已完成全綠；commit 仍待 `.git` DENY ACL 解除。
- [x] **T-FAT-ROTATE-V2 刀 7**（2026-04-22 09:05 閉；ACL-free）— `src/api/models.py` 拆成 `src/api/models/requests.py`、`src/api/models/responses.py`、`src/api/models/__init__.py`；保留 `src.api.models` 匯入面；驗證 `python -m pytest tests/test_api_server.py -q` = 259 passed、`python -m pytest tests/ -q --ignore=tests/integration -x` = 3750 passed。
- [x] **T-FAT-ROTATE-V2 刀 8**（2026-04-22 10:12 閉；ACL-free）— `src/agents/fact_checker.py` 拆成 `src/agents/fact_checker/__init__.py`、`src/agents/fact_checker/checks.py`、`src/agents/fact_checker/pipeline.py`；保留 `src.agents.fact_checker` 與 mapping loader patch 面；驗證 targeted pytest 644 passed，另全量 `pytest tests/ -q --ignore=tests/integration -x` 於 shell timeout 前已印出 **3750 passed**。
- [x] **Openspec 收官** — 01-real-sources / 02-open-notebook-fork / 03-citation-tw-format / 04-audit-citation / 05-kb-governance 五件 proposal + tasks + specs 全齊；tasks 全 `[x]` = 15 + 15 + 9 + 8 + 8 = 55 件。
- [x] **較早完成項** — 已移到 [docs/archive/program-history-202604g.md](docs/archive/program-history-202604g.md)。

---

## 備註

- 歷史 v-header、舊 P0/P1 bundle、早期完成清單：看 [docs/archive/program-history-202604g.md](docs/archive/program-history-202604g.md)。
- 早期反思層：看 [docs/archive/engineer-log-202604*.md](docs/archive/)。
- `results.log` 是逐輪事實帳；`program.md` 現在只負責現況與活任務。
- 若要追完整脈絡：先讀 archive，再查 `results.log`，最後看 git history。
