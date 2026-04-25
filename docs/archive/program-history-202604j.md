# Program History Archive — v7.0 / v7.1 / v7.2 Sensor Headers

> Archived 2026-04-25 from program.md v7.4 trim (T-PROGRAM-MD-TRIM)

> **🎯 v7.0 架構師第四十一輪階段性規劃（2026-04-22；/pua 阿里味；caveman；T-PROGRAM-MD-ARCHIVE 落地 + 第四十二輪 /pua 獨立 sensor 校準）**：
>
> **HEAD 獨立實測指標（`wc + find + grep + git log` 本輪現跑；ACL-free）**：
> - ✅ Spectra 5/5 = 100%（01-05 Epic proposal + tasks + specs 全齊）
> - ✅ 胖檔收斂：`src/` 內 >400 行 Python **0 檔**（本輪拆 `cli/kb/rebuild.py 572 → 356`）
> - ✅ 邊界 watch：`web_preview/app 399 / api/routes/workflow/_execution 389 / knowledge/realtime_lookup 386 / knowledge/fetchers/law_fetcher 377 / core/constants 374`
> - 🟠 裸 except **實測 109 處 / 61 檔**（v7.0 header 寫 127/64 stale；HEAD `grep -rEc "except Exception|except:" src/` 為準）
> - 🟠 裸 except 高密度前 9 檔 = `web_preview/app 7 / kb/stats 6 / manager 5 / gazette 4 / _manager_search 4 / core/llm 4 / generate/export 4 / agents/fact_checker 4 / auditor 4` 共 42 處 / 38.5%
> - 🟡 corpus = **173**（P2-CORPUS-300 連 3 輪 0 動；MOHW live diag 連 4 輪 0 動）
> - ✅ program.md = **190 行**（v6.4 下 1912 → 190 真砍，archive 真落地）
> - ✅ engineer-log = **208 行**（`docs/archive/engineer-log-202604g.md` 已落；T9.6-v5 已閉）
> - 🔴 auto-commit 語意率 **1/30 = 3.3%**（連 >42 輪 Admin-dep；ACL DENY SID 2 條持平）
> - ✅ pytest 新基線：`3750 passed / 0 failed / 630.18s`（2026-04-22 09:00 左右重跑；runtime ≤ 500s 仍是 v8.0 目標）
>
> **v7.0 P0 重排（第四十二輪 /pua 精校；連 1 輪延宕 = 紅線 X 3.25）**：
> 1. ✅ **T9.6-REOPEN-v5**（2026-04-22 已閉）— `engineer-log.md` 已封存到 `docs/archive/engineer-log-202604g.md`，主檔 `208` 行回到 hard cap 內
> 2. ✅ **T-FAT-ROTATE-V2 刀 7**（2026-04-22 09:05 閉；ACL-free）— `src/api/models.py 461` 已拆 `src/api/models/{__init__, requests, responses}.py`；`from src.api.models import *` 契約守；`pytest tests/test_api_server.py -q` + `pytest tests/ -q --ignore=tests/integration -x` 全綠
> 3. ✅ **T-BARE-EXCEPT-AUDIT 刀 4**（2026-04-22 已閉；ACL-free）— `src/core/llm.py`、`src/knowledge/fetchers/gazette_fetcher.py`、`src/knowledge/_manager_search.py` 裸 except 已清零；`pytest tests/test_llm.py tests/test_fetchers.py tests/test_knowledge_manager_unit.py -q` 契約守
> 4. 🟡 **T-PYTEST-RUNTIME-FIX** → **P1 降級**（30 分；profile 已存 `docs/pytest-profile-v6.4.md`；P0 三件完結後開工）— 前 30 慢點（cite_cmd cp950 / KB search / agent timeout / fetcher retry）對症；目標 runtime ≤ 500s
> 5. ✅ **T-PROGRAM-MD-ARCHIVE-REAL**（2026-04-22；前輪閉）— 頭部 16 疊歷史 header 真清到 archive；主檔 1912 → 190
>
> **v7.0 P1（連 2 輪延宕 = 3.25）**：
> 6. 🟡 **EPIC6-DISCOVERY**（30 分；連 2 輪空缺；Spectra 100% 後首 epic）— `openspec/changes/06-*/proposal.md` 骨架；本輪建議選 `live-ingest quality gate`（最貼合 corpus 擴量 + FDA/MOHW 血債）
> 7. 🟡 **T-COMMIT-SEMANTIC-GUARD**（45 分；ACL-free 部分可先落）— `scripts/commit_msg_lint.py` + pre-commit hook；拒絕 `auto-commit: checkpoint` 裸格式；補 `docs/commit-plan.md` v3
> 8. 🟡 **P0.1-MOHW-LIVE-DIAG**（15 分；連 4 輪 0 動 → 本輪不動即 3.25 硬實錘 → 下輪強制降 P2 或 15 min curl 完結）
>
> **v7.0 下輪硬指標（第四十二輪收尾審查）**：
> 1. `wc -l engineer-log.md` ≤ 300（當前 208 ✅）
> 2. `wc -l program.md` ≤ 250（當前 ≈ 200 ✅ 守錨點）
> 3. `wc -l src/api/models.py` 或拆後 `src/api/models/*.py` 每檔 ≤ 400（當前 `requests.py 181 / responses.py 83 / __init__.py 45` ✅）
> 4. `grep -rEc "except Exception|except:" src/web_preview/app.py src/cli/kb/stats.py src/knowledge/manager.py` 合計 ≤ 5（當前 18）
> 5. 裸 except 總數 ≤ 90（當前 109）
> 6. `find kb_data/corpus -name "*.md" | wc -l` ≥ 200（當前 173）
> 7. pytest runtime ≤ 700s（當前 960s；middle target）
> 8. `ls openspec/changes/06-*/proposal.md` 存在（EPIC6 錨點；連 3 輪空缺即降 P2）
> 9. auto-commit 語意率 ≥ 20%（近 30 commits 至少 6 條語意；當前 3.3%）
> 10. `ls docs/archive/engineer-log-202604g.md` 存在（T9.6-v5 錨點）
>
> **紅線狀態**：核心 3 + 實戰 X 不變；第四十二輪 /pua 反思發現 v7.0 header 裸 except 計數 stale（127→實測 109），方法論紅線新增 = **下輪所有 grep/wc/find 必須 HEAD 獨立跑**，不用 header 當事實源；`P2-CORPUS-300`、`MOHW live diag`、Nemotron validate 三件 Admin/key 依賴，**若三輪再不動全體降 P2 或塞 Legacy**；auto-commit 洪水結構性紅不動如山。

> **v7.0-sensor 校準段（2026-04-22 03:50；第四十二輪深度回顧 HEAD 獨立 sensor）**：
> - ✅ **T-BARE-EXCEPT-AUDIT 刀 3 無聲閉環**（results.log 03:06 PASS）— 18 處已落；v7.0 header P0 三位 stale；本輪降 [x]。
> - ✅ **P0-TEST-REGRESSION 閉**（03:41 PASS）— pytest 基線 **3741 → 3745 passed**（+4）；KnowledgeBaseManager Chroma 降級處理。
> - ✅ **engineer-log 已壓回 208**（`docs/archive/engineer-log-202604g.md` 新增；T9.6-REOPEN-v5 關閉）
> - 🟠 **裸 except 熱點遷移**：新 TOP 9 = `gazette_fetcher 4 / _manager_search 4 / core/llm 4 / generate/export 4 / fact_checker 4 / auditor 4 / _manager_hybrid 3 / reviewers 3 / config_tools 3`。
> - 🟠 **fact_checker.py 446 漏列 fat-rotate**（v7.0 header 胖檔清單有列，但未排任務）— **新 P0 刀 8** 鎖定。
> - 🟡 **TODO/FIXME 97 處未盤點**（首次入 sensor；下 epoch T-TODO-AUDIT 治理題）。
> - 🟡 **auto-commit 語意率 2/30 = 6.7%**（近 30 條：v7.0 規劃 + P0-TEST-REGRESSION 兩條語意）。
>
> **v7.1 P0 精校（本輪新增刀 4 + 刀 8）**：
> 1. ✅ **T9.6-REOPEN-v5** 已閉（engineer-log 208；主檔重回 cap 內）
> 2. ✅ **T-FAT-ROTATE-V2 刀 7** 已閉（api/models 已拆 package；requests 181 / responses 83 / __init__ 45）
> 3. ✅ **T-BARE-EXCEPT-AUDIT 刀 4** 已閉（`core/llm` / `gazette_fetcher` / `_manager_search` 裸 except = 0）
> 4. ✅ **T-FAT-ROTATE-V2 刀 8** 已閉（fact_checker 已拆 package；`__init__ 30 / checks 257 / pipeline 205`）

> **v7.2-sensor 校準段（2026-04-25 02:18；第四十三輪深度回顧 HEAD 獨立 sensor；header 連 2 輪漂白抓現行）**：
> - ✅ **pytest 本輪全量 3790 passed / 192.74s / exit 0**（上輪 340 → -43.6%；**內部目標 ≤ 300s 達標**，裕量 107s）— 推斷 auto-engineer `_manager_hybrid.py` BM25 cap + 前輪 `cc5ac3c`/`c0933f9` 合力砍出；下輪 session 起手重跑驗證 noise
> - 🔴 **header 連 2 輪漂白**：bare except 實測 **89 處 / 61 檔**（header 寫 109；-18% 未同步）；auto-commit 語意率 **25/30 = 83.3%**（header 寫 3.3% = 完全離譜）；fat-watch 名單漏 `api/routes/agents 397`
> - 🔴 **工作樹 M `_manager_hybrid.py` 未 commit**：auto-engineer BM25 query cap 500 字（DoS 保護）diff 清晰；違反「M 檔案不過夜」北極星規則
> - 🟠 **裸 except 熱點再遷移（新 TOP）**：`_manager_hybrid 3 / reviewers 3 / config_tools 3 / workflow/_endpoints 3 / editor/__init__ 3 / compliance_checker 3` = 18 處；前輪刀 1-5 清掉舊熱點後集中於這 6 檔
> - 🟠 **胖檔連 N 輪破錨點**：`datagovtw.py 410` 仍 > 400（v7.0 硬指標 ≤ 400）；新現 `api/routes/agents.py 397` 逼近紅線
> - 🟡 **冰山第 3 型新分類**（T-TEST-LOCAL-BINDING-AUDIT）：auto-engineer BM25 query cap = **DoS / 效能漏洞型**；補前輪第 1 型（`from X import Y`）/ 第 2 型（外部服務漏 mock）分類
> - 🟡 **ACL DENY vs commit 成功矛盾**：`icacls .git` 仍顯示外來 SID DENY，但近 30 commits 100% 落地 → P0.D 前提錯；需校準或降 P2
> - 🟡 **EPIC6 T-LIQG-1..12 全 [ ] 連 1 輪 0 動**：骨架 `33bf8ce` 後無實作；與 corpus 173 擴量互為死結
>
> **v7.2 P0 精校（本輪新增刀 10/11/12 + sensor refresh）**：
> 1. ✅ **T-WORKTREE-CLEAN**（2026-04-25 02:20 閉；`1eef399` BM25 cap 已入；working tree clean）
> 2. 🔴 **T-HEADER-SENSOR-REFRESH**（連 2 輪漂白，紅線升級每輪第 0 步）
> 3. 🟠 **T-BARE-EXCEPT-AUDIT 刀 6**（新熱點 6 檔 × 3 處 = 18 處 → 目標總量 ≤ 80）
> 4. 🟠 **T-FAT-ROTATE-V2 刀 10**（`datagovtw.py 410` 拆 package）
> 5. 🟡 **T-ACL-STATE-RECALIBRATE**（ACL DENY 前提校準）
