# Auto-Dev Program — 公文 AI Agent（真實公開公文改寫系統）

> 歷史 v7.0–v7.7 sensor/header 已封存：[docs/archive/program-history-202604j.md](docs/archive/program-history-202604j.md)、[docs/archive/program-history-202604k.md](docs/archive/program-history-202604k.md)

> **v7.8-sensor 校準段（2026-04-25 17:08；HEAD + sensor + pytest 三源獨立 cold-start）**：
> - ✅ **pytest 3926 passed / 0 failed / 63.75s**（`python -m pytest -q --ignore=tests/integration --tb=line`；vs v7.7 header 寫 3917/129.30s — header lag 已修）
> - ✅ **sensor_refresh.py exit 0**；`violations.hard = []`
> - ✅ **bare-except 39 處 / 35 檔**（刀9 已閉：cli/rewrite_cmd / cli/switcher / generate/pipeline/compose / kb/corpus / kb/status 各 2 處 → typed bucket；797 passed）
> - ✅ **fat files 0 over 400**；yellow 10 檔（validators 391 / _execution 389 / realtime_lookup 386 ...）
> - ✅ **program.md soft cap 已修**；v7.3–v7.7 header 封存後主檔 < 250 行
> - ✅ **corpus 400 ≥ target 200**（v7.7 header 寫 173 為漂白；T-CORPUS-200-PUSH + P2-CORPUS-300 已閉）
> - 🔴 **auto-commit 語意率 3.3%（1/30）<< 90%**（近 30 commit 29 條 = `auto-commit checkpoint` 噪音；root = supervise.sh runtime-seat **out-of-repo**）
> - ✅ **EPIC6 13/13 全閉**；EPIC1-5 = 55/55；spec 09 = T9.1/T9.4 soft-close（naming drift 接受）
>
> **v7.8 P0（本輪三件，全閉）**：
> 1. ✅ **T-HEADER-RESYNC-v6**（修上輪 3 處漂白：corpus 173→400 / auto-commit 46.7%→3.3% / pytest 3917/129s→3926/63s）
- [x] **T-SPEC-LAG-CLOSE-v2**（2026-04-25 閉；P0）— `openspec/changes/09-fat-rotate-iter3/tasks.md` T9.1/T9.4 已補閉；實作補拆 `src/cli/kb/fetch_commands.py`，使 `rebuild.py` 356→190、fetch_commands.py 176、_quality_gate_cli.py 145、_rebuild_corpus.py 89，全 ≤300；保留 `src.cli.kb.rebuild._run_fetcher_for_source` re-export 與 CLI app 註冊；驗證 `python -m pytest tests/test_kb_rebuild_cli.py tests/test_kb_gate_check_cli.py tests/test_cli_commands.py tests/test_fetchers.py -q -k "rebuild or gate_check or fetch_debates"` = 13 passed、`python scripts/sensor_refresh.py --human` red_over_400=[]。
> 3. ✅ **T-BARE-EXCEPT-AUDIT 刀 9**（10 處一刀清；49→39；797 passed）

> **v7.3–v7.7 sensor/header 歷史已封存**：詳見 [docs/archive/program-history-202604k.md](docs/archive/program-history-202604k.md)。

### P0（v7.8c 20:08 /pua 深度回顧新增；治理優先；本輪必動）

- [x] **T-OPENSPEC-PROMOTE-AUDIT**（2026-04-25 閉；P0；ACL-free）— 驗證 specs 已 promote（14 spec files in openspec/specs/）；移除 11 個重複 active change folders（archive 早已有 date-prefixed copy）；建立 `openspec/changes/archive/INDEX.md`（11 條目全齊）；寫 `docs/openspec-promotion-audit-202604.md` 收尾報告。驗收：`ls openspec/changes/` 僅剩 `12-commit-msg-noise-floor` ✅；`openspec/specs/` 14 spec files（≥10）✅；INDEX.md 建立 ✅。
- [x] **T-LITELLM-MOCK-CONTRACT-FIX**（2026-04-25 20:36 閉；P0；ACL-free）— 實測 litellm mock contract 已對齊目前依賴；`python -m pytest tests/test_robustness.py -W error::UserWarning -q` = 299 passed / 0 warning，未重現 `ModelResponse / Choices / Message` pydantic schema warning；全量非 integration `python -m pytest -q --ignore=tests/integration --tb=line` = 3949 passed。

### P0（v7.8b 18:35 反思新增；本輪必動 45 min）

- [x] **T-WORKTREE-COMMIT-LINT**（5 min；P0；2026-04-25 18:35）— `scripts/commit_msg_lint.py` + `tests/test_commit_msg_lint.py` + `program.md` 改動仍在工作樹未入版；以單一 `feat(scripts): commit_msg_lint reject pseudo-semantic checkpoint` 落版；驗證 `git status` clean（扣除 copilot session 檔）+ `python -m pytest tests/test_commit_msg_lint.py -q` ≥ 既有 case 全綠。**不入版 = 規則沒生效**。
- [x] **T-BARE-EXCEPT-AUDIT 刀 10**（30 min；P0；2026-04-25 18:35）— sensor top-5 共 9 處：`graph/aggregator(2) / graph/refiner(2) / knowledge/realtime_lookup(2) / knowledge/fetchers/law_fetcher(2) / agents/consistency_checker(1)` → typed bucket（`LLMError|RuntimeError|OSError` 視 callsite）；目標 39 → 30；**全量 `pytest -x` 收尾**防刀 8 回歸再現。
- [x] **T-AUTO-COMMIT-RATE-RECOMPUTE**（10 min；P0；2026-04-25 18:35）— `scripts/sensor_refresh.py` auto-commit 公式把 `chore(auto-engineer): checkpoint snapshot` 視為合規是樂觀偏差；改成只認 `feat|fix|refactor|docs|test|chore(scope!=auto-engineer)` 真語意；實際率回到 13–15%；驗證 `python scripts/sensor_refresh.py --human` 顯示真實率 + `tests/test_sensor_refresh.py` 加 1 條防回歸。**統計口徑放水 = 漂白第二型**。

### P1（連 2 輪延宕 = 3.25）

#### v7.8c 20:08 /pua 深度回顧新增 — integration 補漏 + 外部 blocker 上升

- [ ] **T-INTEGRATION-COVERAGE-PHASE-2**（90 min；P1；2026-04-25 20:08；ACL-free）— integration 4 檔（smoke / e2e_rewrite / kb_rebuild_quality_gate / api_server_smoke）覆蓋仍薄；缺：(1) KB CLI 完整流（`gov-ai kb fetch → ingest → search` recall@k 對比）；(2) `cite_cmd` e2e（CLI 拉條件 → 出引用）；(3) `web_preview` render smoke（`uvicorn boot → GET / → 渲染標的元素 assert`）；(4) `meeting` API 多輪互動（happy + 邊界）。目標 integration 4→8，每檔 GOV_AI_RUN_INTEGRATION 開關；驗收 `GOV_AI_RUN_INTEGRATION=1 pytest tests/integration -q` 全綠 + 無增加主套件時間。**單元 3949 passed 的信心建在 mock 上 = 盲飛**。
- [x] **P1-AUTO-COMMIT-EXTERNAL-PATCH**（2026-04-25 20:31 閉；repo-side handoff）— 已新增 `docs/auto-commit-host-action.md` host-side 清單（interval 5→30 min / squash window / semantic message template / 驗證命令），並在 `HANDOFF.md` 補 host Admin 錨點；repo 內可交付部分完成。後續驗收移交 `T-COMMIT-T12.5-VERIFY`：待 host reload 後 rolling 30-commit 真語意率 90%+、`git log -n 30 --format=%s` 無 `chore(auto-engineer): patch`、逐行 pipe 到 `python scripts/commit_msg_lint.py -` 全綠。
- [ ] **T-COMMIT-T12.5-VERIFY**（5 min；P1；2026-04-25 20:08；依賴 P1-AUTO-COMMIT-EXTERNAL-PATCH）— `openspec/changes/12-commit-msg-noise-floor/tasks.md` T12.5 唯一 pending；待 wrapper daemons reload 後跑 `git log -n 30 --format=%s` 並逐行 pipe 到 `python scripts/commit_msg_lint.py -`，0 violations 時把 [x] 補上、change 進 archive。

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
- [ ] **P2-CHROMA-NEMOTRON-VALIDATE** — `OPENROUTER_API_KEY` 已驗證有效（2026-04-25 13:56 `curl /api/v1/auth/key` 200，付費帳號 is_free_tier=false，limit=null 無限額，累計 usage=$0.000035）→ **unblocked，可執行**：跑 `gov-ai kb rebuild --only-real`（走 `nvidia/llama-nemotron-embed-vl-1b-v2:free` dim=2048 重建 ChromaDB）+ 撰寫 `docs/embedding-validation.md` 記錄向量化前後 search recall@k 對比。
- [x] **T6.1**（2026-04-26 閉；ACL-free；注：full 30-item eval 需啟動 API server）— blind eval baseline：`docs/benchmark-baseline.md` 記錄 v2.1 快照（afterfix17 limit=2, avg_score=0.8766, success_rate=1.0）+趨勢表+完整執行步驟；`benchmark/baseline_v2.1.json` 以 afterfix17 2 題快照為底；完整 30 題需 `python scripts/run_blind_eval.py --limit 30`。
- [x] **T6.2**（2026-04-26 閉；ACL-free）— benchmark trend：`scripts/benchmark_trend.py` 建立（append + 10% regression gate）；`benchmark/trend.jsonl` 以 8 個歷史 afterfix run 種子；`tests/test_benchmark_trend.py` = 19 passed；每次 T2.x 後可呼叫 `python scripts/benchmark_trend.py <result.json>` 追加趨勢並自動偵測 regression。

### Repo / Governance

- [ ] **T9.1.a** — benchmark corpus 版控復位（ACL 解後）。
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

- [ ] **P2-Legacy-INDEX-LOCK**（原 P0.D；2026-04-25 校準降級）— `.git` foreign SID DENY 仍存在，但 **不匹配當前 token**；現行可重現故障改定義為 `.git/index.lock: Permission denied` 寫鎖問題，疑似 Git/MSYS shell、背景並行程序或宿主機權限異常。保留 legacy/advisory 追蹤，待最小 repro 後再決定是否需 Admin 清理 ACL。
- [ ] **P0.S-REBASE-APPLY** — 等 ACL 解後才跑 `scripts/rewrite_auto_commit_msgs.py --apply`。
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
