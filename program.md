# Auto-Dev Program — 公文 AI Agent（真實公開公文改寫系統）

> **🎯 v7.0 架構師第四十一輪階段性規劃（2026-04-22；/pua 阿里味；caveman；T-PROGRAM-MD-ARCHIVE 落地 + 第四十二輪 /pua 獨立 sensor 校準）**：
>
> **HEAD 獨立實測指標（`wc + find + grep + git log` 本輪現跑；ACL-free）**：
> - ✅ Spectra 5/5 = 100%（01-05 Epic proposal + tasks + specs 全齊）
> - ✅ 胖檔收斂：`src/` 內 >400 行 Python **2 檔** = `sources/datagovtw 410 / cli/workflow_cmd 406`
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

> **v7.3-sensor 校準段（2026-04-25 02:45；第四十四輪深度回顧；HEAD 全獨立跑）**：
> - ✅ **pytest cross-session cold-start = 3801 passed / 152.98s / exit 0**（破下 epoch ≤ 200s 目標 47s 裕量；BM25 cap 真效非 cache 假象確認；演進 960→773→547→461→340→343→179→173→**153s** 累計 -84%）
> - 🔴 **engineer-log 351 行** 破 300 hard cap 51 行（T9.6-v6 才閉 4 天就再犯 → v7 強制本輪）
> - 🔴 **header 連 2 輪漂白**：bare except 寫 109 / 實測 **89 處 / 58 檔**；auto-commit 寫 3.3% / 實測 **86.7%**（26/30；但近 5 條 2/5 惡化）；fat-watch 漏 `api/routes/agents 397`
> - 🔴 **P0.D ACL 前提錯**：7+ 輪誤歸「SID DENY」，實測 AUTO-RESCUE 每輪代 commit 全通 → T-ACL-STATE-RECALIBRATE 升 P0 硬落
> - 🟠 **auto-commit 再犯 2 次**（本 session 內）：`6eb9907 / 96c9d05`；共 4 次違規（含 `c53a947 / 1eef399`）→ T-AUTO-COMMIT-SEMANTIC **升 P0**
> - 🟠 **胖檔破錨點**：`datagovtw 410 / web_preview 399 / api/routes/agents 397 / validators 391 / workflow/_execution 389`
> - 🟡 **Spectra 06 = 2/13 閉**（T-LIQG-1 quality_gate.py + T-LIQG-2 quality_config.py 已落；T-LIQG-3/4/5 待 → P1 啟動）
> - 🟡 **T-PYTEST-COLLECT-NAMESPACE 已閉**（`6eb9907`；conftest.py + tests/__init__.py + tests/integration/__init__.py）
> - 🟡 **synthetic flag 155/192 = 80.7%**（37 份未覆蓋首次入 sensor → P1 T-SYNTHETIC-AUDIT）

> **v7.3 P0（本輪新增 + 升級）**：
> 1. 🔴 **T9.6-REOPEN-v7**（engineer-log 351→≤100 封存 v7.0/v7.1/v7.2 到 `docs/archive/engineer-log-202604i.md`；T9.6-v6 之後 4 天重犯）
> 2. 🔴 **T-HEADER-SENSOR-REFRESH**（`scripts/sensor_refresh.py` 本輪必 commit；連 3 輪漂白 = 3.25 X 3）
> 3. 🔴 **T-ACL-STATE-RECALIBRATE**（升 P0；P0.D 前提錯 7+ 輪）
> 4. 🔴 **T-AUTO-COMMIT-SEMANTIC**（升 P0；4 次違規現行犯）
> 5. 🟠 **T-BARE-EXCEPT-AUDIT 刀 6**（沿用）
> 6. 🟠 **T-FAT-ROTATE-V2 刀 10**（datagovtw）+ **刀 11**（api/routes/agents 397 新加）

---

## 🚨 北極星指令（優先於所有判斷）

**每輪啟動後第一動作**（v2.8 糾偏順序）：
1. `icacls .git 2>&1 | grep -i DENY | head -3` → 若有 DENY ACL，**本輪進入 read-only 模式**
2. `git status --short | wc -l` 看工作樹是否乾淨
3. **ACL 乾淨 + 工作樹乾淨** → 從「待辦」挑第一個 `[ ]` 未勾任務執行
4. **ACL 有 DENY** → 只能跑標為 ✅ read-only 的任務，禁止任何 `git add/commit`
5. **v2.8 新增**：read-only 任務本質是「working tree write + document」；不要把「寫檔」誤判為需要 commit

### 🔴 執行守則（整併 ACL / PASS / 延宕 / 骨架規則）
- **ACL-gated**：當 `.git` 存在外來 SID DENY ACL，所有 commit / add / stash 類任務必須標為 `[BLOCKED-ACL]`；不接受「先試一下」
- **PASS 定義**：任何 `[PASS]` 任務都要附 git ls-tree / pytest / ls / rg 等可重跑證據；規劃側勾選不算 PASS
- **延宕升級**：P1+ 任務連 5 輪延宕下輪升 P0；但若根因是 ACL DENY，記 BLOCKED 不升 P0
- **read-only 不得拖**：文件、盤點、純程式碼整理任務連 2 輪延宕 = 3.25；不能拿 ACL 當藉口
- **骨架不是實作**：adapter / seam / proposal 只有骨架不算完成；至少要有 1 條可驗證流程或 fixture/real ingest 證據

### 禁止行為
- ❌ 不要讓 M 狀態檔案累積超過 1 輪
- ❌ 不要先跑 pytest 再決定做什麼
- ❌ 不要改 program.md 最前面 Epic 結構（只能 `[x]` 勾選或搬至「已完成」）
- ❌ **禁用 `auto-commit: checkpoint` 訊息格式**（v2.6 沿用；v7.0 T-COMMIT-SEMANTIC-GUARD 準備強制執行）
- ❌ **ACL 未解前禁試 `git add/commit`**（v2.7 新；產生的 FAIL log 無意義，浪費輪次）

### 任務顆粒度原則
- 每個 `[ ]` 任務 **1 小時內可完成**
- 太大 → 拆子任務 append 到對應 Epic 尾
- 每子任務 → 一個 commit（ACL 解除後）

---

## 專案資訊
- **名稱**: 公文 AI Agent（Gov AI Agent）
- **定位**: 從真實公開政府公文中，找相符範本 → 最小改動改寫 → 可追本溯源
- **技術棧**: Python 3.11+ / Ollama (Llama 3.1 8b) / ChromaDB / click CLI / python-docx
- **根目錄**: `D:/Users/Administrator/Desktop/公文ai agent/`
- **運行模式**: 本地優先，資料源必須真實公開政府公文
- **引擎**: codex (gpt-5.4) 驅動 auto-engineer，L4 自主模式

---

## 核心原則（不可違反）

### 🔴 三條核心紅線
1. **真實性**：知識庫只收真實公開政府公文。`kb_data/examples/` 現有 **155** 份合成公文須標 `synthetic=true`
2. **改寫而非生成**：Writer 以「找最相似真實公文 → 最小改動改寫」為主策略
3. **可溯源**：每份生成公文必須附 `## 引用來源` 段

### 🔴 實戰紅線 X（PASS 定義漂移）
- **承諾漂移**：任務寫進 program.md 卻連續數輪不動
- **方案驅動治理**：只寫方案，不落實作 / 驗證 / 收尾
- **設計驅動治理**：只修 spec / proposal / adapter 表面，不跑完整 pipeline
- **未驗即交**：改完不跑對應測試或 CLI 實證
- **focused smoke 偷全綠**：局部 smoke 綠，卻拿來冒充全量 pytest 綠
- **header lag**：HEAD 已完成，program.md 頂部仍把任務列成未做
- **判定**：任一子條款命中即算紅線 X，記 3.25

### 🟢 合規與授權
- 只抓公開公文；遵守 robots.txt + rate limit ≥2 秒/請求
- 保留 `raw_snapshot` + `source_url` + `crawl_date`
- User-Agent 明示：`GovAI-Agent/1.0 (research; contact: ...)`

---

## 開發規則

### 每次迭代只做一件事
- 從「待辦」挑第一個未完成任務
- 完成後 `[x]` + 追加 `results.log`

### 品質要求
- 新代碼必須有 pytest
- 測試通過 → conventional commit（`feat(sources): add moj law API adapter`）
- 測試失敗 → 最多 3 次修復 → 仍失敗記 log + stash + 跳過
- 架構變動先更新 `docs/architecture.md`

### 禁止事項
- ❌ 不擅自升級依賴
- ❌ 不刪現有 agent
- ❌ 不動 `config.yaml` 結構
- ❌ 不提交含 PII 的真實資料

### 紀錄格式（results.log）
```
[YYYY-MM-DD HH:MM:SS] | [T 任務編號] | [PASS/FAIL/SKIP/BLOCKED-ACL] | 簡述做了什麼 | 相關檔案
```

---

## 當前待辦

### P0（連 1 輪延宕 = 紅線 X 3.25）

- [ ] **T9.6-REOPEN-v7**（10 分；P0；2026-04-25 新；v7.3 反思現行）— engineer-log 351 > 300 hard cap；封存 v7.0 第四十二輪 / v7.1 LOOP2 / v7.2 反思 + LOOP3 開篇 + BM25 task B+2 五段到 `docs/archive/engineer-log-202604i.md`；主檔只留 v7.3 單段（≤ 100 行）；驗證：`wc -l engineer-log.md` ≤ 300、`ls docs/archive/engineer-log-202604i.md`。
- [ ] **T-HEADER-SENSOR-REFRESH**（45 分；P0；2026-04-25 新；連 2 輪漂白 3.25 X 2 → 本輪不落 X 3）— `scripts/sensor_refresh.py`：wc/rg/git/find 全量跑寫回 program.md 頂部 sensor 區塊；列 bare except 總量/TOP 檔、fat-file top 15、auto-commit 語意率、corpus、pytest 最新；掛 loop starter checklist 第 0 步；證據：script 存在 + dry-run 輸出 + 至少一次 commit 重寫 header。
- [x] **T-ACL-STATE-RECALIBRATE**（2026-04-25 03:08 閉；ACL/advisory 校準）— 以 PowerShell `WindowsIdentity` 取當前 SID `S-1-5-21-1271297351-773185924-864452041-500`，確認不匹配 `.git` foreign DENY SID `S-1-5-21-541253457-2268935619-321007557-692795393`，且該 SID 不在當前 token；`git commit --dry-run --allow-empty` 仍重現 `.git/index.lock: Permission denied`、`.git/index` 僅 `A` 屬性。結論：**P0.D 前提錯**，foreign SID DENY 降為 advisory / legacy，現行 blocker 改記 `.git/index.lock` 寫鎖問題；`scripts/check_acl_state.py` 已補 token-aware mismatch 判讀，證據見 `docs/acl-recalibrate-2026-04-25.md`。
- [ ] **T-AUTO-COMMIT-SEMANTIC**（60 分；P0；2026-04-25 升級；4 次違規現行：`6eb9907 / 96c9d05 / c53a947 / 1eef399`）— auto-engineer commit msg generator 改吐 `chore(auto-engineer): <type>-<summary> @<timestamp>`；接 `scripts/commit_msg_lint.py` 驗證（runtime path 視 `index.lock` 問題是否仍阻塞 hook 安裝決定）；若 git 寫鎖真阻塞，改用 `scripts/validate_auto_commit_msg.py` 在 auto-engineer runtime pre-commit 驗；證據：`git log -n 30 --format=%s | grep -v checkpoint` ≥ 30。
- [ ] **T-BARE-EXCEPT-AUDIT 刀 6**（45 分；P0；2026-04-25 新）— 新熱點 6 檔 × 3 處 = 18 處：`src/knowledge/_manager_hybrid.py`、`src/graph/nodes/reviewers.py`、`src/cli/config_tools.py`、`src/api/routes/workflow/_endpoints.py`、`src/agents/editor/__init__.py`、`src/agents/compliance_checker.py`；typed bucket + `logger.warning`；驗證 `rg -c 'except Exception|except:' <files>` 全 0、總量 ≤ 80、pytest 對應測試綠。
- [ ] **T-FAT-ROTATE-V2 刀 10**（30 分；P0；2026-04-25 新）— `src/sources/datagovtw.py 410` 拆 package：`datagovtw/{__init__, reader, normalizer, catalog}.py`；保留 `from src.sources.datagovtw import DataGovTwAdapter` 匯入面；驗證 `pytest tests/test_sources*.py -q` 綠 + 每檔 ≤ 300。
- [ ] **T-FAT-ROTATE-V2 刀 11**（30 分；P0；2026-04-25 新；v7.3 sensor 新發現）— `src/api/routes/agents.py 397` 拆 package：`agents/{__init__, read_routes, write_routes}.py` 或按職責拆；保留 FastAPI router 掛載路徑；驗證 `pytest tests/test_api_server.py -q -k agent` 綠 + 每檔 ≤ 300。
- [x] **T-WORKTREE-CLEAN**（2026-04-25 02:20 閉；commit `1eef399`）— `_manager_hybrid.py` BM25 query cap 500 字（DoS 保護）已入 AUTO-RESCUE；`git status --short` = 0 行；`git log --format=%s -n 5 | grep -i BM25` 命中 `1eef399` auto-commit checkpoint（訊息違規另計 T-AUTO-COMMIT-SEMANTIC）。冰山第 3 型首患者閉。
- [x] **T-BARE-EXCEPT-AUDIT 刀 5**（2026-04-22 12:16 閉；ACL-free）— `src/cli/generate/export.py`、`src/agents/auditor.py` 8 處裸 except 改 typed bucket + `logger.warning`；補 `_export_qa_report` / lint / cite / auditor logging 回歸；驗證 `python -m pytest tests/test_export_citation_metadata.py tests/test_exporter_extended.py tests/test_agents.py tests/test_agents_extended.py -q` = 369 passed、`rg -n "except Exception|except:" src/cli/generate/export.py src/agents/auditor.py` = 0 命中。
- [x] **T-FAT-ROTATE-V2 刀 9**（2026-04-22 13:18 閉；ACL-free）— `src/cli/workflow_cmd.py 345` 拆為 `src/cli/workflow_cmd/{__init__,commands,helpers}.py`（44 / 258 / 66）；保留 `from src.cli.workflow_cmd import app`、`_ensure_dir`、`_workflow_path`、`_validate_workflow_name` 契約與 monkeypatch 面；驗證 `python -m pytest tests/test_workflow_cmd.py -q` = 35 passed、`python -m pytest tests/test_cli_state_dir.py tests/test_cli_commands.py -q -k workflow` = 21 passed。
- [x] **T-COMMIT-SEMANTIC-GUARD**（2026-04-24 16:22 閉；commit `2678b10`；ACL-free）— `scripts/commit_msg_lint.py`（117 行）拒絕 `auto-commit: checkpoint` / `WIP` / 單字 placeholder，要求 Conventional Commit prefix + subject ≥ 10；`tests/test_commit_msg_lint.py` = 19 passed / 0.56s；`docs/commit-plan.md` 重寫為 v3 正式契約（11 types + enforcement + ACL-blocked hook 路徑）；v2.2 封存至 `docs/archive/commit-plans/2026-04-20-v2.2-split.md`。hook wire 待 P0.D 解 ACL 後落地，短期 CI + session 自律兜底。
- [x] **T9.6-REOPEN-v5**（2026-04-22 04:05 閉；ACL-free）— 封存 `v5.7 / v5.8 / v5.9 / v6.0` 反思到 `docs/archive/engineer-log-202604g.md`；`engineer-log.md` 主檔收斂為 `v6.1→v6.2 / v6.3 / v7.0 / v7.0-sensor`；`wc -l engineer-log.md` = 208。
- [x] **T-BARE-EXCEPT-AUDIT 刀 3**（2026-04-22 03:06 閉；ACL-free）— `src/web_preview/app.py 7` + `src/cli/kb/stats.py 6` + `src/knowledge/manager.py 5` = 18 處 / 3 檔已收斂 typed bucket + `logger.warning`；補 logging 回歸測試；pytest 3741 / 0 / 778s 全綠；結構性 typed-bucket 模板沿用刀 1/2 成熟。
- [x] **T-BARE-EXCEPT-AUDIT 刀 4**（2026-04-22 04:29 閉；ACL-free）— `src/core/llm.py`、`src/knowledge/fetchers/gazette_fetcher.py`、`src/knowledge/_manager_search.py` 12 處裸 except 已收斂為 typed bucket + `logger.warning`；`rg -n "except Exception|except:"` 三檔 = 0 命中。
- [x] **T-FAT-ROTATE-V2 刀 8**（2026-04-22 10:12 閉；ACL-free）— `src/agents/fact_checker.py 446` 拆成 `src/agents/fact_checker/{__init__, checks, pipeline}.py`；保留 `src.agents.fact_checker`、`FactChecker`、`_MAPPING_PATH`、`_load_regulation_doc_type_mapping` 匯入面；`tests/test_fact_checker_coverage.py tests/test_fact_checker_enhanced.py tests/test_agents.py tests/test_agents_extended.py tests/test_api_server.py tests/test_realtime_lookup.py -q` = 644 passed。
- [x] **P0-TEST-REGRESSION**（2026-04-22 03:41 閉；ACL-free）— `src/knowledge/manager.py` 對 corrupted Chroma persisted config + opaque vendor exception 降級處理；新增 `_type` KeyError 回歸；pytest **3741 → 3745 passed**（+4 測試）；基線刷新。
- [x] **T-PROGRAM-MD-ARCHIVE-REAL**（2026-04-22；前輪）— 頭部 v5.5-v6.4 歷史 header 真封存至 `docs/archive/program-history-202604g.md`；主檔收斂到 v7.0 單 header + 規則 + 活任務。

### P1（連 2 輪延宕 = 3.25）

- [ ] **T-TEST-LOCAL-BINDING-AUDIT**（P1 升級；2026-04-25 從下 epoch 提級）— 冰山三型系統性對策：ast-grep rule 掃所有 `from src.api.dependencies import` + `from src.knowledge.realtime_lookup import` + 外部服務實例化點；CONTRIBUTING.md 規範章節；`tests/conftest.py` 全域 re-bind helper；驗證 `scripts/audit_local_binding.py --dry-run` 列出剩餘候選患者。
- [ ] **T-PYTEST-RUNTIME-FIX-v3**（P1；2026-04-25）— 本輪 **cross-session cold-start = 152.98s / 3801 passed**（新 session 獨立起跑，**破 ≤ 200s 目標 47s 裕量，BM25 cap 真效確認**）；**升級目標 ≤ 120s**（差 33s，待 `test_safe_score / meeting_exporter` 同類患者掃完）；守穩條件：下輪起手 cold-start > 180s 即 regression 回查。
- [x] **EPIC6 T-LIQG-4**（2026-04-25 02:59 閉；本輪）— `gov-ai kb rebuild --quality-gate` 已接到 active corpus rebuild：先按來源批次 gate，任何 named failure 即中止，成功才進 only-real merge；補 `tests/test_kb_rebuild_cli.py` 驗證 PASS/FAIL 兩條路，`python -m pytest tests/test_kb_rebuild_cli.py tests/test_kb_gate_check_cli.py -q -k gate` = 6 passed。**P2-CORPUS-300 擴量前置再少一刀**。
- [ ] **EPIC6 T-LIQG-5**（P1；2026-04-25 新）— `docs/quality-gate-failure-matrix.md` 4 named error 三角表 + triage + `--require-live` 交互；驗證 `rg -n "LiveIngestBelowFloor|SchemaIntegrityError|StaleRecord|SyntheticContamination" docs/quality-gate-failure-matrix.md` 全命中。
- [ ] **T-SYNTHETIC-AUDIT**（P1；2026-04-25 新；v7.3 sensor 首入）— `kb_data/examples/` 192 份 vs `synthetic=true` 155 份差 37 份未覆蓋；稽核 37 份真實性並標 `synthetic=true/false` 明確；驗證 `python scripts/audit_synthetic_flag.py --strict` exit 0；與 T-LIQG-1 `SyntheticContamination` 檢測契合，為 CORPUS-300 擴量掃雷。
- [x] **EPIC6 T-LIQG-1**（2026-04-25 02:20 閉；commit `c53a947` auto-engineer 吃 checkpoint 格式）— `src/sources/quality_gate.py`（171 行）+ `tests/test_quality_gate.py`（99 行）：`QualityGate.evaluate` + 4 named failure 合約落地。⚠️ auto-engineer commit message 違反 T-COMMIT-SEMANTIC-GUARD（用 `auto-commit: checkpoint` 裸格式），T-AUTO-COMMIT-SEMANTIC 升 P0 處理。
- [x] **T-PYTEST-RUNTIME-FIX**（2026-04-24 本輪四段對症；全部達標）— (1) 2026-04-22 11:03 `src/cli/main.py` help-only boot gate (28.84s → 0.43s)；(2) 第四十一輪 `f2fc2ad` + `adb531c fix(test): preflight re-bind` 修 StopIteration flake + `src.api.app.get_config` local binding；(3) **本輪 `cc5ac3c perf(tests)` autouse `_no_fetcher_backoff_sleep` 清 6 × 7s retry backoff = 42s**；(4) **本輪 `6b41335 perf(tests)` patch `src.api.routes.workflow.get_llm/get_kb` local binding — meeting_exporter 119.77s → 2.53s 省 117s**。runtime 演進：**960s → 773s → 547s → 461.20s → 340.21s (-64.5% vs 開局)**。3790 passed / 5:40。**LOOP2 ≤ 700s ✅（裕量 360s）+ 內部 ≤ 500s ✅ + 下 epoch 新目標 ≤ 300s 只差 40s**。新 Top 1 `TestEditorSafeLowNoRefine::test_safe_score_no_auto_refine` 12.54s + `TestKBEdgeCases::test_search_very_long_string` 11.27s 留給 **T-TEST-LOCAL-BINDING-AUDIT**（冰山法則：所有 `from src.api.dependencies import ...` 的 module local binding 掃一遍同類 patch bypass）。
- [ ] **P2-CORPUS-300**（待 mojlaw/datagovtw/executive_yuan_rss/pcc live 續抓）— corpus 173 → 300；`scripts/live_ingest.py --sources mojlaw,datagovtw,executive_yuan_rss,pcc --limit 100 --require-live --prune-fixture-fallback`。
- [x] **P0.1-MOHW-LIVE-DIAG**（2026-04-24 17:01 閉；commit `7c46761`）— `docs/mohw-endpoint-probe.md`（128 行）實測：endpoint HTTP 200 / 25511 bytes / 1.20s / feed 10 items / today 2026-04-24 新聞 / `fixture_fallback=False` / `synthetic=False`；列 4 個已知限制（`source_doc_no` URL fallback / description HTML 含 `<style>` 塊 / RSS TTL 20min vs freshness_window / 無分頁無歷史）全部跨引到 EPIC6 T-LIQG-2 / T-LIQG-3 backlog；手動 probe 3 步驟 SOP + 失敗排查表。本 session live adapter call 獨立驗證：`MohwRssAdapter().list(limit=5)` 0.53s / 5 entries / cache 20 / 所有 normalize() OK。

### P2（Admin/key 依賴，不能當 P1 佔坑）

- [x] **EPIC6-DISCOVERY**（2026-04-24 16:58 閉；commit `33bf8ce`）— `openspec/changes/06-live-ingest-quality-gate/` proposal (43) + tasks (82) + `specs/quality-gate/spec.md` (111) = 236 行骨架；3 dimensions（volume floor / schema integrity / provenance signal）× 4 named failures（LiveIngestBelowFloor / SchemaIntegrityError / StaleRecord / SyntheticContamination）+ 5 個 T-LIQG-1..5 後續 tasks（gate 模組 + CLI + 失敗矩陣 doc）。
- [ ] **P2-CHROMA-NEMOTRON-VALIDATE** — 待人工填 `OPENROUTER_API_KEY` 後跑 `gov-ai kb rebuild --only-real` + `docs/embedding-validation.md`。
- [ ] **T6.1** — blind eval baseline：`run_blind_eval.py --limit 30` + `benchmark/baseline_v2.1.json` + `docs/benchmark-baseline.md`。
- [ ] **T6.2** — benchmark trend：每次 T2.x 後追加 `benchmark/trend.jsonl`；跌幅 >10% 即 regression gate。

### Repo / Governance

- [ ] **T9.1.a** — benchmark corpus 版控復位（ACL 解後）。
- [x] **T9.2**（2026-04-24 16:25 閉；commit `400130d`）— atomic tmp source/lock/cleanup audit 三層（`src/cli/utils.py` atomic_text/json/yaml_write；root `.gitignore` `.json_*.tmp` / `.txt_*.tmp` / `.yaml_*.tmp` pattern；`tests/conftest.py` session-autouse `_cleanup_stale_atomic_tmps` fixture）寫成 `docs/atomic-tmp-audit.md`；pytest `test_cli_utils_tmp_cleanup.py` = 3 passed / 0.31s。
- [x] **T9.3**（2026-04-24 閉；commit `2678b10`）— `docs/commit-plan.md` v2.2 已封存至 `docs/archive/commit-plans/2026-04-20-v2.2-split.md`（111 行）；主檔原位重寫為 v3 搭配 T-COMMIT-SEMANTIC-GUARD。
- [x] **T9.5**（2026-04-24 閉；commit `a838fd3` 前輪已落）— root 遺留 `.ps1/.docx` 歸位到 `scripts/legacy/`；本輪 `Get-ChildItem *.ps1 *.docx` root count = 0 + `scripts/legacy/` 實存 10 支 `.ps1`，header lag 補勾。
- [x] **T7.3**（2026-04-24 16:30 閉；commit `3ac5c90`）— `docs/engineer-log-spec.md`（104 行）定義 section format（三證自審 + 事故+處置 + 下輪錨點 + PUA 旁白）、soft cap 300 / hard cap 400、lifecycle append-only + 月檔封存（`engineer-log-YYYYMM<letter>.md`）、與 `program.md` / `results.log` 的角色分工。
- [x] **T10.2**（2026-04-24 16:30 閉；commit `3ac5c90` auto-engineer 版 superset；ACL-free）— `scripts/check_auto_engineer_state.py`（205 行）解析 `.auto-engineer.state.json` + **PID liveness check**（`os.kill(0)` / Windows `tasklist`），6 狀態 running/idle/stale/orphan/absent/malformed + 修復建議字串；`tests/test_check_auto_engineer_state.py` = 8 passed；實測本機 status=**orphan**（PID 17644 dead + state "running"，age 51h）建議 lock orphan + mark stale + allow pua-loop takeover。本 session 同時寫的 `check_autoengineer_stall.py` 子集（129 行，只看時間戳 5 狀態）因為重複實作被刪除（commit `51e6d5e` → 本 commit dedup）。T7.3 `docs/engineer-log-spec.md` 同 commit 順帶閉環。
- [x] **T10.4**（2026-04-24 16:28 閉；commit `e475169`）— `scripts/check_acl_state.py` 解析 `icacls .git` + 信任 SID 白名單（Administrators/SYSTEM/AuthUsers/本機 SID prefix）、輸出 JSON 報告 + exit 0/1 + `--human`；`tests/test_check_acl_state.py` = 8 passed；實測 status=denied deny_count=2（P0.D 未解）可作 pua-loop / auto-engineer 啟動 gate。

### 下 epoch 錨點（LOOP2+ 開出）

- [ ] **T-TEST-LOCAL-BINDING-AUDIT**（部分閉；2026-04-24~25 修 4 個患者）— 冰山分**三型**：
  - **第 1 型**（`from X import Y` module local binding）：`adb531c` preflight `src.api.app.get_config` + `6b41335` `workflow.get_llm/get_kb` — 2 個患者已修
  - **第 2 型**（外部服務實例化 `_ensure_cache` 漏 HTTP mock）：`c0933f9` conftest preload empty `realtime_lookup` caches — 1 個患者 `test_safe_score 44s → 0.11s`
  - **第 3 型**（產品代碼缺大輸入保護 / DoS 向量）：`1eef399` `_manager_hybrid.py` BM25 query length cap 500 字 — 1 個患者 `test_search_very_long_string 7.95s → 1.00s`（**production + test 同時受惠**）
  - **剩餘候選**：`TestSwitchCommand::test_switch_direct_provider` 2.4-3.3s / `TestWebUIGenerate` 系列 2.5-3.2s（需分類為哪一型再對症）
  - **系統性對策**（下 epoch）：ast-grep rule 掃 `from src.api.dependencies import` + `from src.knowledge.realtime_lookup import` + 外部服務 `__init__` 內 HTTP 調用 + production 函式缺 input length cap；CONTRIBUTING.md 規範章節；`tests/conftest.py` 全域 re-bind helper；`scripts/audit_local_binding.py --dry-run` 列候選
- [ ] **T-PYTEST-RUNTIME-FIX-v3** — 目標 ≤ 300s（現雙 baseline **179/173s** 已破；守穩住下輪 cold-start 若 > 220s = regression）
- [ ] **T-AUTO-COMMIT-SEMANTIC** ⬆ **升 P0**（2026-04-25 auto-engineer 再犯 2 次 `1eef399 / c53a947` checkpoint 裸格式）— auto-engineer commit msg generator 改吐 `chore(auto-engineer): <type>-<summary> @<timestamp>`；過 `scripts/commit_msg_lint.py` 才准 commit；hook 強制執行
- [ ] **EPIC6 T-LIQG-5 + coverage 收尾** — T-LIQG-1..4 已落（見上），剩 `docs/quality-gate-failure-matrix.md` + spectra requirement-coverage（T-LIQG-6..12）收尾

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

- [x] **T-PYTEST-COLLECT-NAMESPACE**（2026-04-25 02:38 閉；ACL-free）— 修正 `tests/test_e2e_rewrite.py` 與 `tests/integration/test_e2e_rewrite.py` 同名導致的 pytest collect 衝突；新增 `tests/__init__.py`、`tests/integration/__init__.py` 與 root `conftest.py` 相容 shim，保住舊有 `from conftest import ...` 匯入；驗證 `python -m pytest tests/test_e2e_rewrite.py tests/integration/test_e2e_rewrite.py -q` = 5 passed、`python -m pytest tests/test_api_auth.py tests/test_api_server.py tests/test_e2e.py tests/test_stress.py -q` = 383 passed、`python -m pytest tests -q` = 3802 passed / 10 skipped。
- [x] **EPIC6 T-LIQG-3**（2026-04-25 02:53 閉；ACL-free）— `gov-ai kb gate-check --source <name>` 已接到 `src/cli/kb/rebuild.py`，走 source adapter fresh fetch + `QualityGate.from_adapter_name()`，支援 `--format human|json` 成功報告與 named failure JSON；新增 `tests/test_kb_gate_check_cli.py` 覆蓋 human/json success、`--since` 傳遞與 `SyntheticContamination` fail。驗證 `python -m pytest tests/test_kb_gate_check_cli.py -q` = 4 passed、`python -m pytest tests/test_cli_commands.py -q -k "kb_rebuild or kb_ingest or kb_search"` = 18 passed。
- [x] **EPIC6 T-LIQG-4**（2026-04-25 02:59 閉；本輪）— `gov-ai kb rebuild --quality-gate` 已接到 active corpus rebuild：先對每個 adapter 批次跑 gate，再進 only-real merge；gate 失敗時 stderr 輸出 structured JSON 並中止，不跑後續 adapter。新增 `tests/test_kb_rebuild_cli.py` 覆蓋 PASS/FAIL 兩路；驗證 `python -m pytest tests/test_kb_rebuild_cli.py tests/test_kb_gate_check_cli.py -q -k gate` = 6 passed。
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
