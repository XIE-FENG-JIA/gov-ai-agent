# Auto-Dev Program — 公文 AI Agent（真實公開公文改寫系統）

> **🎯 v7.0 架構師第四十一輪階段性規劃（2026-04-22；/pua 阿里味；caveman；T-PROGRAM-MD-ARCHIVE 真正落地）**：
>
> **HEAD 實測指標（wc + find + grep + git log 即取；ACL-free）**：
> - ✅ pytest 基線：`3741 passed / 0 failed`（`docs/pytest-profile-v6.4.md` 記 841.51s / 960.04s 兩次實測）
> - 🟠 pytest runtime 連兩輪翻倍 `238 → 549 → 772 → 960s`；CI 體感 -30%；T-PYTEST-PROFILE 已落但根因收斂未做
> - ✅ Spectra 5/5 = 100%（01-05 Epic proposal + tasks + specs 全齊，tasks 全 `[x]`）
> - ✅ 胖檔收斂：`src/` 內 >400 行 Python 從 8 → **4 檔**（`api/models 461 / fact_checker 446 / datagovtw 410 / workflow_cmd 406`）
> - 🟠 裸 except `127 處 / 64 檔`（上輪 136/65；production routes 清零後血債轉向 web_preview / kb/stats / manager）
> - 🟡 corpus = **173**（P2-CORPUS-300 連 3 輪 0 動；MOHW live diag 連 4 輪 0 動）
> - 🔴 engineer-log = **336 行** 破 300 hard cap（v5.7/v5.8 / v6.1 / v6.4 反思層疊加）
> - 🔴 auto-commit 語意率 **1/30 = 3.3%**（連 >40 輪 Admin-dep；ACL DENY SID 2 條持平）
> - ✅ program.md = 469 → **本輪重寫後預期 ≤ 200**（頂部 v5.5-v6.4 歷史 header 正式封存至 `docs/archive/program-history-202604g.md`）
>
> **v7.0 P0 重排（連 1 輪延宕 = 紅線 X 3.25）**：
> 1. ✅ **T-PROGRAM-MD-ARCHIVE-REAL**（本輪做）— 頭部 16 疊歷史 header 真清到 archive；主檔 469 → ≤ 200 行
> 2. 🔴 **T9.6-REOPEN-v5**（10 分；ACL-free）— engineer-log 336 > 300；封存 v5.7/v5.8 / v6.0 到 `docs/archive/engineer-log-202604g.md`；主檔留 v6.1 以降
> 3. 🟠 **T-FAT-ROTATE-V2 刀 7**（40 分；ACL-free）— `src/api/models.py 461` 按 request / response schema 拆 package；`from src.api.models import *` 契約守
> 4. 🟠 **T-BARE-EXCEPT-AUDIT 刀 3**（45 分；ACL-free；合併三檔）— `web_preview/app 7` + `kb/stats 6` + `manager 5` = 18 處 / 3 檔，typed bucket + logger.warning
> 5. 🟡 **T-PYTEST-RUNTIME-FIX**（30 分）— 根據 `docs/pytest-profile-v6.4.md` 前 30 慢點（cite_cmd cp950 / KB search / agent timeout / fetcher retry）對症下藥；目標 runtime ≤ 500s
>
> **v7.0 P1（連 2 輪延宕 = 3.25）**：
> 6. 🟡 **EPIC6-DISCOVERY**（30 分；Spectra 100% 後首 epic）— `openspec/changes/06-*/proposal.md` 骨架；候選三題擇一：`live-ingest quality gate` / `audit trail UI` / `observability dashboard`
> 7. 🟡 **T-COMMIT-SEMANTIC-GUARD**（45 分；auto-commit 洪水根因）— `scripts/commit_msg_lint.py` + pre-commit hook；拒絕 `auto-commit: checkpoint` 裸格式；補 `docs/commit-plan.md` v3
> 8. 🟡 **P0.1-MOHW-LIVE-DIAG**（15 分；連 4 輪 0 動 → 本輪不動即 3.25 硬實錘 → 降 P2 或做一次）
>
> **v7.0 下輪硬指標**：
> 1. `wc -l program.md` ≤ 250
> 2. `wc -l engineer-log.md` ≤ 300
> 3. `wc -l src/api/models.py` 或拆後 `src/api/models/*.py` 每檔 ≤ 400
> 4. `grep -c "except Exception\|except:" src/web_preview/app.py src/cli/kb/stats.py src/knowledge/manager.py` 合計 ≤ 5（當前 18）
> 5. `find kb_data/corpus -name "*.md" | wc -l` ≥ 200（當前 173；下一里程碑 300）
> 6. pytest runtime ≤ 700s（當前 960s；middle target，500s 為 v8.0 目標）
> 7. `ls openspec/changes/06-*/proposal.md` 存在
> 8. auto-commit 語意率 ≥ 20%（近 30 commits 至少 6 條語意）
>
> **紅線狀態**：核心 3 + 實戰 X 不變；v7.0 不新增紅線；`P2-CORPUS-300`、`MOHW live diag`、Nemotron validate 三件 Admin/key 依賴，**若三輪再不動全體降 P2 或塞 Legacy**，避免殭屍 P1；auto-commit 洪水結構性紅不動如山。

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

- [x] **T-PROGRAM-MD-ARCHIVE-REAL**（2026-04-22；本輪）— 頭部 v5.5-v6.4 歷史 header 真封存至 `docs/archive/program-history-202604g.md`；主檔收斂到 v7.0 單 header + 規則 + 活任務。
- [ ] **T9.6-REOPEN-v5**（10 分；ACL-free）— engineer-log.md 336 > 300 hard cap；封存 v5.7/v5.8/v6.0 / 早於 v6.1 的反思到 `docs/archive/engineer-log-202604g.md`；主檔留 v6.1/v6.3/v6.4/v7.0。
- [ ] **T-FAT-ROTATE-V2 刀 7**（40 分；ACL-free）— `src/api/models.py 461` 按 request/response schema 邊界拆 `src/api/models/{__init__, requests, responses}.py`；`from src.api.models import *` 匯入面守；`tests/test_api_*.py` 契約守。
- [ ] **T-BARE-EXCEPT-AUDIT 刀 3**（45 分；ACL-free；三檔合併）— `src/web_preview/app.py 7` + `src/cli/kb/stats.py 6` + `src/knowledge/manager.py 5` = 18 處 / 3 檔；typed bucket + `logger.warning` SOP 複製 `routes/agents.py` v6.3 刀 2。
- [ ] **T-PYTEST-RUNTIME-FIX**（30 分）— 根據 `docs/pytest-profile-v6.4.md` 前 30 慢點（`cite_cmd cp950`、KB search、agent timeout path、fetcher network-error retry）對症下藥；目標 runtime ≤ 500s；CI 體感 blocker。

### P1（連 2 輪延宕 = 3.25）

- [ ] **EPIC6-DISCOVERY**（30 分；Spectra 100% 後下槓桿）— `openspec/changes/06-*/proposal.md` 骨架；候選三題擇一：`live-ingest quality gate`（ingest 後 schema/robots/license 自動校驗）、`audit trail UI`（citation + source lineage 視覺化）、`observability dashboard`（pytest runtime / API latency / corpus growth trend）。
- [ ] **T-COMMIT-SEMANTIC-GUARD**（45 分；auto-commit 洪水根因）— `scripts/commit_msg_lint.py` 拒絕 `auto-commit: checkpoint` 裸格式；pre-commit hook + `docs/commit-plan.md` v3；auto-engineer 必須帶語意 subject。
- [ ] **P2-CORPUS-300**（待 mojlaw/datagovtw/executive_yuan_rss/pcc live 續抓）— corpus 173 → 300；`scripts/live_ingest.py --sources mojlaw,datagovtw,executive_yuan_rss,pcc --limit 100 --require-live --prune-fixture-fallback`。
- [ ] **P0.1-MOHW-LIVE-DIAG**（15 分；連 4 輪 0 動 → 本輪不動即降 P2 或一次處理完）— `MohwRssAdapter` live fetch 診斷；複製 FDA probe SOP；交付 `docs/mohw-endpoint-probe.md`。

### P2（Admin/key 依賴，不能當 P1 佔坑）

- [ ] **P2-CHROMA-NEMOTRON-VALIDATE** — 待人工填 `OPENROUTER_API_KEY` 後跑 `gov-ai kb rebuild --only-real` + `docs/embedding-validation.md`。
- [ ] **T6.1** — blind eval baseline：`run_blind_eval.py --limit 30` + `benchmark/baseline_v2.1.json` + `docs/benchmark-baseline.md`。
- [ ] **T6.2** — benchmark trend：每次 T2.x 後追加 `benchmark/trend.jsonl`；跌幅 >10% 即 regression gate。

### Repo / Governance

- [ ] **T9.1.a** — benchmark corpus 版控復位（ACL 解後）。
- [ ] **T9.2** — tmp 再生源頭排查；鎖 `.json_*.tmp` / `.txt_*.tmp`。
- [ ] **T9.3** — `docs/commit-plan.md` 歸檔到 `docs/archive/commit-plans/2026-04-20-v2.2-split.md`。
- [ ] **T9.5** — root 遺留 `.ps1/.docx` 歸位。
- [ ] **T7.3** — `engineer-log.md` 版控與 append 規範整理（建議併入 T9.6-REOPEN-v5）。
- [ ] **T10.2** — auto-engineer 延宕 gate；動 `.auto-engineer.state.json`。
- [ ] **T10.4** — 啟動先檢 `icacls .git | grep -c DENY`；有 DENY 就切 read-only 任務池。

### Legacy / Frozen

- [ ] **P0.D** — `.git` 外來 SID DENY ACL；需人工 Admin 清理。
- [ ] **P0.S-REBASE-APPLY** — 等 ACL 解後才跑 `scripts/rewrite_auto_commit_msgs.py --apply`。
- [ ] **P1.3（T2.0.a）** — `.env` + litellm smoke；ACL/key gating。
- [ ] **T2.3** — SurrealDB migration；凍結。
- [ ] **T2.5** — API 層融合；保留 legacy backlog。
- [ ] **T2.7-old / T2.8-old / T2.9-old** — 舊 Epic 2 條目；保留追蹤，不列本輪首要。
- [ ] **T5.2 / T5.3** — Epic 5 長尾：500 份 real corpus 後 rebuild；ChromaDB 停役仍凍結。
- [ ] **P0.GG** — Windows gotchas 文檔補完；非 blocker。
- [ ] **P0.SELF-COMMIT-REFLECT** — 仍受 ACL 現況牽制；保留為治理題。
- [ ] **T1.6** — 已併入 corpus 擴量路線；保留原編號方便追歷史。

---

## 已完成

- [x] **近期閉環（2026-04-22）** — `T-PROGRAM-MD-ARCHIVE`、`T-PROGRAM-MD-ARCHIVE-REAL`、`T-PYTEST-PROFILE`、`T-ROLLUP-SYNC`、`T-FAT-ROTATE-V2` 刀 3/4/5/6、`T9.6-REOPEN-v4`、`T-BARE-EXCEPT-AUDIT` 刀 1/2、`P1-PCC-ADAPTER`、`P0.1-FDA-LIVE-DIAG`、`P0.3-CORPUS-SCALE`、`EPIC5-TASKS-SPECS`、`T5.1`、`T5.2`、`T5.3`、`T5.4`。
- [x] **Openspec 收官** — 01-real-sources / 02-open-notebook-fork / 03-citation-tw-format / 04-audit-citation / 05-kb-governance 五件 proposal + tasks + specs 全齊；tasks 全 `[x]` = 15 + 15 + 9 + 8 + 8 = 55 件。
- [x] **較早完成項** — 已移到 [docs/archive/program-history-202604g.md](docs/archive/program-history-202604g.md)。

---

## 備註

- 歷史 v-header、舊 P0/P1 bundle、早期完成清單：看 [docs/archive/program-history-202604g.md](docs/archive/program-history-202604g.md)。
- 早期反思層：看 [docs/archive/engineer-log-202604*.md](docs/archive/)。
- `results.log` 是逐輪事實帳；`program.md` 現在只負責現況與活任務。
- 若要追完整脈絡：先讀 archive，再查 `results.log`，最後看 git history。
