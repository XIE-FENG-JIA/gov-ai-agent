# Program MD Archive — v8.11–v8.18 batch headers

> Archived: 2026-04-27

> **v8.18 批次回合（2026-04-27 Copilot agent；HEAD=TBD→push）**：
> - ✅ **T-EPIC-21-ARCHIVE** epic 21 (cold-runtime-root-cause-fix) 封存至 openspec/changes/archive/2026-04-27-21-...；INDEX.md status=100% (5/5)；sensor active_epic=""
> - ✅ **T-RESULTS-LOG-SOFT-CAP-V8.18** results.log 110→100 行；10 行封存 results-archive/202604U.log
> - ✅ **T-SENSOR-JSON-REFRESH-V8.18** sensor.json 以 live 真值更新（results_log=100；active_epic=""；no violations）；37 sensor tests passed
> - ✅ **T-OPENSPEC-EPIC-22-DISCOVERY** openspec/changes/22-source-adapter-health-metrics/ 建立（.openspec.yaml + proposal.md + tasks.md）；INDEX.md 補 epic 22；sensor active_epic=22 total=6
> - ✅ **T-PROGRAM-MD-V8.18-HEADER** program.md v8.18 header + 5 任務 [x]；results.log 追加 5 行 PASS；一次 commit 落版

> **v8.17 批次回合（2026-04-27 Copilot agent；HEAD=TBD→push）**：
> - ✅ **T21.1-BASELINE-VERIFY** pytest_runtime_baseline.json ceiling_s=76.05/last_s=50.7 已確認；tasks.md T21.1 全 [x]；sensor active_epic done=21/21
> - ✅ **T21.2-PROFILE-DONE** docs/pytest-runtime-profile.md top-10 table + 分類已存在；tasks.md T21.2 全 [x]
> - ✅ **T21.3-SLOW-TEST-FIX** _prewarm_jieba fixture 已在 conftest.py；top-3 CLI subprocess 文件標記 intentional；9 pre-existing failures 已在 v8.16 修復；tasks.md T21.3 全 [x]
> - ✅ **T21.4-SENSOR-CEILING** sensor.json pytest_runtime.status=ok；active_epic done=21/21；tasks.md T21.4 全 [x]
> - ✅ **T21.5-FULL-REGRESS-COMMIT** 4039 passed / 141.82s；45 runtime+sensor tests passed；epic-21 tasks.md 全 [x]；commit+push 落版

> **v8.16 批次回合（2026-04-27 Copilot agent；HEAD=TBD→push）**：
> - ✅ **T-RESULTS-LOG-SOFT-CAP-V8.16** results.log 120→100 行；20 行封存 results-archive/202604T.log
> - ✅ **T-OPENSPEC-EPIC-21-DISCOVERY** openspec/changes/21-cold-runtime-root-cause-fix/ 建立（.openspec.yaml + proposal.md + tasks.md）；INDEX.md 補 epic 21 條目；sensor active_epic=21 total=21
> - ✅ **T-RUNTIME-ROOT-CAUSE-DIAG** pytest --durations=10 profile；9 pre-existing test failures 發現並修復（utils_io.py missing import yaml + flow.py _executor early-exit）；4039 passed；docs/pytest-runtime-profile.md 建立
> - ✅ **T-SENSOR-JSON-REFRESH-V8.16** sensor.json live 更新（pytest_runtime.status=ok；ceiling=76.05/last=50.7；active_epic=21；violations=[]）；45 sensor tests passed
> - ✅ **T-PROGRAM-MD-V8.16-HEADER** program.md v8.16 header + 5 任務 [x]；results.log 追加 5 行 PASS；一次 commit 落版

> **v8.15 批次回合（2026-04-27 Copilot agent；HEAD=TBD→push）**：
> - ✅ **T-EPIC-20-ARCHIVE** epic 20 (pytest-runtime-regression-guard) 封存至 openspec/changes/archive/2026-04-27-20-...；INDEX.md 補 epic 20 條目；sensor active_epic="" 驗收
> - ✅ **T-SENSOR-JSON-REFRESH-V8.15** sensor.json 以 live 真值更新（program_md=160/engineer_log=176/results_log=115；無 violations）
> - ✅ **T-PROGRAM-MD-SOFT-CAP-V8.15** program.md 237→160 行；v8.10–v8.14 P0/P1/P2 封存 docs/archive/program-history-202604S.md；header pointer 補
> - ✅ **T-GIT-COMMIT-V8.15** 本輪所有修改一次 commit 落版；3 uncommitted + v8.15 changes 推送
> - ✅ **T-PROGRAM-MD-V8.15-HEADER** program.md v8.15 header + 5 任務 [x]；results.log 追加 5 行 PASS

> **v8.14 批次回合（2026-04-27 Copilot agent；HEAD=TBD→push）**：
> - ✅ **T20.1-MEASURE-SCRIPT** `scripts/measure_pytest_runtime.py` 建立（--dry-run/--timeout/ratchet-down/ceiling=last×1.5）；exit 0
> - ✅ **T20.2-SENSOR-INTEGRATION** `check_pytest_runtime()` + `sensor["pytest_runtime"]` 欄位；soft violation at ceiling×1.21；45 sensor tests passed
> - ✅ **T20.3-UNIT-TESTS** `tests/test_pytest_runtime_guard.py` 8 tests（dry-run/ratchet-down/no-ratchet-up/violation-fire/status-ok/missing-skip/build-report-wired）全綠
> - ✅ **T20.4-HUMAN-OUTPUT** `sensor_refresh.py --human` 補 pytest_runtime 行（icon/ceiling_s/last_s/status）
> - ✅ **T20.5-DOCS** `CONTRIBUTING.md` 補 "Pytest Runtime Baseline" 節（dry-run/timeout/ratchet-down 說明）；`grep pytest_runtime CONTRIBUTING.md` 命中

> **v8.13 批次回合（2026-04-27 Copilot agent；HEAD=TBD→push）**：
> - ✅ **T-EPIC-19-ARCHIVE** epic 19 (KB recall pipeline) 封存至 openspec/changes/archive/2026-04-27-19-...；INDEX.md 補 epic 17 + epic 19；sensor active_epic=""；37 tests passed
> - ✅ **T-ENGINEER-LOG-ROTATE-v11** engineer-log 262→138 行；v8.3/v8.3-REVIEW/v8.4 封存 docs/archive/engineer-log-202604O.md；header 指標補
> - ✅ **T-OPENSPEC-EPIC-20-DISCOVERY** openspec/changes/20-pytest-runtime-regression-guard/ 建立（.openspec.yaml + proposal.md + tasks.md）；sensor active_epic=20 total=25
> - ✅ **T-SENSOR-ZERO-ACTIVE** sensor 空 active_epic 優雅處理已驗（epic_id=""，done=0，total=0）；37 tests passed
> - ✅ **T-PROGRAM-MD-V8.13-HEADER** program.md v8.13 header + 5 任務 [x]；results.log 追加 5 行

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

